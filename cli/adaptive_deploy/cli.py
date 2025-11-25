#!/usr/bin/env python3
"""
Adaptive Deploy CLI
Production-ready command-line interface for deployment management
"""
import sys
import json
from typing import Optional, List
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from .client import APIClient, DeploymentCreate, DeploymentControl

console = Console()


@click.group()
@click.option('--api-url', envvar='ADO_API_URL', default='http://localhost:8000',
              help='API server URL')
@click.option('--token', envvar='ADO_TOKEN', help='Authentication token')
@click.pass_context
def main(ctx, api_url: str, token: Optional[str]):
    """
    Adaptive Deployment Orchestrator CLI

    Manage Blue-Green and Canary deployments from the command line.
    """
    ctx.ensure_object(dict)
    ctx.obj['client'] = APIClient(api_url, token)


@main.command()
@click.option('--username', prompt=True, help='Username')
@click.option('--password', prompt=True, hide_input=True, help='Password')
@click.pass_context
def login(ctx, username: str, password: str):
    """Login and obtain authentication token"""
    client = ctx.obj['client']

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Authenticating...", total=None)

        try:
            token = client.login(username, password)
            console.print(f"[green]✓[/green] Login successful!")
            console.print(f"\nToken: [cyan]{token}[/cyan]")
            console.print("\nExport this token:")
            console.print(f"[yellow]export ADO_TOKEN={token}[/yellow]")
        except Exception as e:
            console.print(f"[red]✗[/red] Login failed: {str(e)}", style="bold red")
            sys.exit(1)


@main.group()
def canary():
    """Canary deployment commands"""
    pass


@canary.command('deploy')
@click.option('--service', required=True, help='Service name')
@click.option('--version', required=True, help='Target version')
@click.option('--environment', type=click.Choice(['development', 'staging', 'production']),
              default='staging', help='Target environment')
@click.option('--steps', default='10,25,50,100', help='Canary steps (comma-separated)')
@click.option('--metric', multiple=True, help='Metric to monitor (format: name:threshold)')
@click.option('--namespace', default='default', help='Kubernetes namespace')
@click.option('--auto-start/--no-auto-start', default=False,
              help='Automatically start deployment')
@click.pass_context
def canary_deploy(ctx, service: str, version: str, environment: str, steps: str,
                  metric: tuple, namespace: str, auto_start: bool):
    """
    Deploy using Canary strategy

    Example:
        adaptive-deploy canary deploy \\
            --service news-api \\
            --version v2.0.0 \\
            --metric error_rate:0.05 \\
            --metric latency_p99:1000 \\
            --auto-start
    """
    client = ctx.obj['client']

    # Parse steps
    canary_steps = [int(s.strip()) for s in steps.split(',')]

    # Parse metrics
    metrics_config = {}
    for m in metric:
        if ':' in m:
            name, threshold = m.split(':', 1)
            metrics_config[name] = {
                'threshold': float(threshold),
                'comparison': 'less_than' if name == 'error_rate' else 'less_than'
            }

    deployment_data = {
        'service_name': service,
        'target_version': version,
        'environment': environment,
        'strategy': 'canary',
        'namespace': namespace,
        'canary_steps': canary_steps,
        'metrics_config': metrics_config if metrics_config else None
    }

    console.print(Panel.fit(
        f"[bold cyan]Canary Deployment[/bold cyan]\n\n"
        f"Service: [yellow]{service}[/yellow]\n"
        f"Version: [yellow]{version}[/yellow]\n"
        f"Environment: [yellow]{environment}[/yellow]\n"
        f"Steps: [yellow]{steps}[/yellow]\n"
        f"Metrics: [yellow]{len(metrics_config)}[/yellow]",
        title="Deployment Configuration"
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Creating deployment...", total=None)
            deployment = client.create_deployment(deployment_data)

        console.print(f"[green]✓[/green] Deployment created: [cyan]{deployment['deployment_id']}[/cyan]")

        if auto_start:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Starting deployment...", total=None)
                client.start_deployment(deployment['deployment_id'])

            console.print(f"[green]✓[/green] Deployment started")
            console.print(f"\nMonitor: [cyan]adaptive-deploy status --deployment {deployment['deployment_id']}[/cyan]")
        else:
            console.print(f"\nStart: [cyan]adaptive-deploy start --deployment {deployment['deployment_id']}[/cyan]")

    except Exception as e:
        console.print(f"[red]✗[/red] Deployment failed: {str(e)}", style="bold red")
        sys.exit(1)


@main.group()
def blue_green():
    """Blue-Green deployment commands"""
    pass


@blue_green.command('deploy')
@click.option('--service', required=True, help='Service name')
@click.option('--version', required=True, help='Target version')
@click.option('--environment', type=click.Choice(['development', 'staging', 'production']),
              default='staging', help='Target environment')
@click.option('--namespace', default='default', help='Kubernetes namespace')
@click.option('--auto-start/--no-auto-start', default=False,
              help='Automatically start deployment')
@click.pass_context
def blue_green_deploy(ctx, service: str, version: str, environment: str,
                      namespace: str, auto_start: bool):
    """
    Deploy using Blue-Green strategy

    Example:
        adaptive-deploy blue-green deploy \\
            --service news-api \\
            --version v2.0.0 \\
            --environment production \\
            --auto-start
    """
    client = ctx.obj['client']

    deployment_data = {
        'service_name': service,
        'target_version': version,
        'environment': environment,
        'strategy': 'blue_green',
        'namespace': namespace
    }

    console.print(Panel.fit(
        f"[bold cyan]Blue-Green Deployment[/bold cyan]\n\n"
        f"Service: [yellow]{service}[/yellow]\n"
        f"Version: [yellow]{version}[/yellow]\n"
        f"Environment: [yellow]{environment}[/yellow]",
        title="Deployment Configuration"
    ))

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Creating deployment...", total=None)
            deployment = client.create_deployment(deployment_data)

        console.print(f"[green]✓[/green] Deployment created: [cyan]{deployment['deployment_id']}[/cyan]")

        if auto_start:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Starting deployment...", total=None)
                client.start_deployment(deployment['deployment_id'])

            console.print(f"[green]✓[/green] Deployment started")

    except Exception as e:
        console.print(f"[red]✗[/red] Deployment failed: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.option('--deployment', required=True, help='Deployment ID')
@click.pass_context
def start(ctx, deployment: str):
    """Start a pending deployment"""
    client = ctx.obj['client']

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Starting deployment...", total=None)
            result = client.start_deployment(deployment)

        console.print(f"[green]✓[/green] Deployment started: {result['status']}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to start: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.option('--deployment', required=True, help='Deployment ID')
@click.option('--reason', help='Reason for pausing')
@click.pass_context
def pause(ctx, deployment: str, reason: Optional[str]):
    """Pause a running deployment"""
    client = ctx.obj['client']

    try:
        control_data = {'action': 'pause', 'reason': reason}
        result = client.control_deployment(deployment, control_data)
        console.print(f"[green]✓[/green] Deployment paused: {result['status']}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to pause: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.option('--deployment', required=True, help='Deployment ID')
@click.pass_context
def resume(ctx, deployment: str):
    """Resume a paused deployment"""
    client = ctx.obj['client']

    try:
        control_data = {'action': 'resume'}
        result = client.control_deployment(deployment, control_data)
        console.print(f"[green]✓[/green] Deployment resumed: {result['status']}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to resume: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.option('--deployment', required=True, help='Deployment ID')
@click.option('--reason', prompt=True, help='Reason for rollback')
@click.pass_context
def rollback(ctx, deployment: str, reason: str):
    """Rollback a deployment"""
    client = ctx.obj['client']

    if not click.confirm(f'Are you sure you want to rollback {deployment}?'):
        return

    try:
        control_data = {'action': 'rollback', 'reason': reason}
        result = client.control_deployment(deployment, control_data)
        console.print(f"[green]✓[/green] Deployment rolled back: {result['status']}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to rollback: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.option('--deployment', help='Specific deployment ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all deployments')
@click.option('--service', help='Filter by service name')
@click.option('--environment', help='Filter by environment')
@click.option('--status', help='Filter by status')
@click.pass_context
def status(ctx, deployment: Optional[str], show_all: bool, service: Optional[str],
           environment: Optional[str], status: Optional[str]):
    """
    Get deployment status

    Examples:
        adaptive-deploy status --deployment news-api-canary-20240101120000
        adaptive-deploy status --all
        adaptive-deploy status --service news-api
    """
    client = ctx.obj['client']

    try:
        if deployment:
            # Show specific deployment
            result = client.get_deployment(deployment)
            console.print(Panel.fit(
                f"[bold]Deployment:[/bold] {result['deployment_id']}\n"
                f"[bold]Service:[/bold] {result['service_name']}\n"
                f"[bold]Status:[/bold] {result['status']}\n"
                f"[bold]Strategy:[/bold] {result['strategy']}\n"
                f"[bold]Traffic:[/bold] {result['current_traffic_percentage']}%\n"
                f"[bold]Version:[/bold] {result['target_version']}\n"
                f"[bold]Environment:[/bold] {result['environment']}",
                title=f"Deployment Status"
            ))
        else:
            # List deployments
            params = {}
            if service:
                params['service_name'] = service
            if environment:
                params['environment'] = environment
            if status:
                params['status'] = status

            result = client.list_deployments(**params)

            table = Table(title="Deployments")
            table.add_column("ID", style="cyan")
            table.add_column("Service", style="yellow")
            table.add_column("Status", style="green")
            table.add_column("Strategy")
            table.add_column("Traffic")
            table.add_column("Environment")

            for dep in result['deployments']:
                table.add_row(
                    dep['deployment_id'][:30] + '...' if len(dep['deployment_id']) > 30 else dep['deployment_id'],
                    dep['service_name'],
                    dep['status'],
                    dep['strategy'],
                    f"{dep['current_traffic_percentage']}%",
                    dep['environment']
                )

            console.print(table)
            console.print(f"\nTotal: {result['total']} deployments")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get status: {str(e)}", style="bold red")
        sys.exit(1)


@main.command()
@click.pass_context
def health(ctx):
    """Check API health status"""
    client = ctx.obj['client']

    try:
        result = client.health_check()
        console.print(Panel.fit(
            f"[bold green]Healthy[/bold green]\n\n"
            f"Version: {result['version']}\n"
            f"Timestamp: {result['timestamp']}",
            title="API Health"
        ))
    except Exception as e:
        console.print(f"[red]✗[/red] Health check failed: {str(e)}", style="bold red")
        sys.exit(1)


if __name__ == '__main__':
    main()
