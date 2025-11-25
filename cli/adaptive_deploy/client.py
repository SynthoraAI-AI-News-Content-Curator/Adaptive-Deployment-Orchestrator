"""
API Client for Adaptive Deploy CLI
"""
import requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


class APIError(Exception):
    """API request error"""
    pass


@dataclass
class DeploymentCreate:
    service_name: str
    target_version: str
    environment: str
    strategy: str
    namespace: str = "default"
    canary_steps: Optional[List[int]] = None
    metrics_config: Optional[Dict] = None


@dataclass
class DeploymentControl:
    action: str
    reason: Optional[str] = None


class APIClient:
    """
    HTTP client for Adaptive Deployment Orchestrator API
    """

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()

        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('detail', str(e))
            except:
                error_msg = str(e)
            raise APIError(f"API error: {error_msg}")
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {str(e)}")

    def login(self, username: str, password: str) -> str:
        """Login and get token"""
        response = self._request(
            'POST',
            '/api/v1/auth/login',
            json={'username': username, 'password': password}
        )
        token = response['access_token']
        self.token = token
        self.session.headers['Authorization'] = f'Bearer {token}'
        return token

    def create_deployment(self, deployment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new deployment"""
        return self._request('POST', '/api/v1/deployments', json=deployment_data)

    def list_deployments(self, **params) -> Dict[str, Any]:
        """List deployments with optional filters"""
        return self._request('GET', '/api/v1/deployments', params=params)

    def get_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Get deployment details"""
        return self._request('GET', f'/api/v1/deployments/{deployment_id}')

    def start_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """Start a deployment"""
        return self._request('POST', f'/api/v1/deployments/{deployment_id}/start')

    def control_deployment(
        self,
        deployment_id: str,
        control_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Control a deployment (pause, resume, rollback, etc.)"""
        return self._request(
            'POST',
            f'/api/v1/deployments/{deployment_id}/control',
            json=control_data
        )

    def get_deployment_events(self, deployment_id: str, limit: int = 100) -> List[Dict]:
        """Get deployment events"""
        return self._request(
            'GET',
            f'/api/v1/deployments/{deployment_id}/events',
            params={'limit': limit}
        )

    def get_deployment_metrics(
        self,
        deployment_id: str,
        metric_names: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get deployment metrics"""
        params = {'metric_names': metric_names} if metric_names else {}
        return self._request(
            'GET',
            f'/api/v1/deployments/{deployment_id}/metrics',
            params=params
        )

    def delete_deployment(self, deployment_id: str) -> None:
        """Delete a deployment"""
        self._request('DELETE', f'/api/v1/deployments/{deployment_id}')

    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        return self._request('GET', '/health')
