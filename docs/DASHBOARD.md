# Dashboard User Guide

Complete guide for using the Adaptive Deployment Orchestrator Dashboard.

## Overview

The Dashboard provides a real-time web interface for monitoring and controlling deployments. Built with React and TypeScript, it offers interactive controls, live updates via WebSocket, and comprehensive deployment visualization.

```mermaid
graph TB
    subgraph "Dashboard UI"
        Login[Login Page]
        List[Deployments List]
        Detail[Deployment Detail]
        Create[Create Deployment]
    end

    subgraph "Backend Services"
        API[REST API]
        WS[WebSocket]
    end

    subgraph "Data"
        Auth[Authentication]
        Deploy[Deployments]
        Metrics[Metrics]
        Events[Events]
    end

    Login --> Auth
    List --> Deploy
    Detail --> Deploy & Metrics & Events
    Create --> Deploy

    List --> API
    Detail --> API & WS
    Create --> API
```

---

## Getting Started

### Access the Dashboard

| Environment | URL |
|-------------|-----|
| Local Development | http://localhost:3000 |
| Docker Compose | http://localhost:3000 |
| Production | https://dashboard.yourdomain.com |

### Login

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant API

    User->>Dashboard: Navigate to dashboard
    Dashboard->>User: Show login page
    User->>Dashboard: Enter credentials
    Dashboard->>API: POST /auth/login
    API-->>Dashboard: JWT Token
    Dashboard->>Dashboard: Store token
    Dashboard->>User: Redirect to deployments
```

**Default Credentials:**

| Username | Password | Role |
|----------|----------|------|
| admin | *(set on first login)* | Admin |

> ⚠️ **Important:** Change the default password immediately after first login!

---

## Dashboard Layout

### Navigation Structure

```mermaid
graph LR
    subgraph "Main Navigation"
        Home[Dashboard]
        Deploys[Deployments]
        Create[Create]
        Settings[Settings]
    end

    subgraph "Deployment Views"
        List[List View]
        Detail[Detail View]
        History[History]
        Metrics[Metrics]
    end

    Home --> Deploys
    Deploys --> List & Detail
    Detail --> History & Metrics
```

### Main Areas

```
┌─────────────────────────────────────────────────────────────────┐
│  Navigation Bar                                    [User] [⚙️]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │  Main Content Area                                     │   │
│  │                                                         │   │
│  │  - Deployments List                                    │   │
│  │  - Deployment Details                                  │   │
│  │  - Create Deployment Form                              │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Status Bar / Notifications                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deployments List

### List View Features

The deployments list provides an overview of all deployments with filtering and sorting capabilities.

```mermaid
graph TD
    subgraph "List View"
        Filters[Filters Panel]
        Table[Deployments Table]
        Pagination[Pagination Controls]
    end

    subgraph "Filters"
        Service[Service Filter]
        Env[Environment Filter]
        Status[Status Filter]
        Date[Date Range]
    end

    subgraph "Table Columns"
        ID[Deployment ID]
        Name[Service Name]
        Strat[Strategy]
        Stat[Status]
        Traffic[Traffic %]
        Time[Timestamp]
        Actions[Actions]
    end

    Filters --> Service & Env & Status & Date
    Table --> ID & Name & Strat & Stat & Traffic & Time & Actions
```

### Status Indicators

| Status | Color | Icon | Description |
|--------|-------|------|-------------|
| Pending | Gray | ⏳ | Deployment created, not started |
| In Progress | Blue | 🔄 | Deployment actively running |
| Paused | Yellow | ⏸️ | Deployment paused at current step |
| Completed | Green | ✅ | Deployment successfully completed |
| Failed | Red | ❌ | Deployment failed |
| Rolled Back | Orange | ↩️ | Deployment was rolled back |

### Filtering Options

**By Service:**
- Select from dropdown of available services
- Free-text search

**By Environment:**
- Development
- Staging
- Production

**By Status:**
- All
- Active (in_progress, paused)
- Completed
- Failed

### Quick Actions

From the list view, you can:

| Action | Icon | Description |
|--------|------|-------------|
| View | 👁️ | Open deployment details |
| Start | ▶️ | Start a pending deployment |
| Pause | ⏸️ | Pause an in-progress deployment |
| Rollback | ↩️ | Rollback the deployment |

---

## Deployment Detail View

### Detail View Components

```mermaid
graph TD
    subgraph "Deployment Detail"
        Header[Header & Status]
        Progress[Progress Indicator]
        Controls[Control Panel]
        Metrics[Metrics Panel]
        Events[Event Log]
        History[History Timeline]
    end

    Header --> Progress
    Progress --> Controls
    Controls --> Metrics & Events & History
```

### Header Section

Displays key deployment information:

```
┌─────────────────────────────────────────────────────────────────┐
│  📦 news-api-canary-20240101120000                              │
│                                                                  │
│  Service: news-api          Strategy: Canary                   │
│  Environment: production    Version: v2.0.0                    │
│  Created by: admin          Started: 2024-01-01 12:00:00       │
│                                                                  │
│  Status: [■■■■■□□□□□] IN PROGRESS - 50% Traffic                │
└─────────────────────────────────────────────────────────────────┘
```

### Progress Visualization

#### Canary Deployment Progress

```mermaid
graph LR
    subgraph "Canary Steps"
        S1[10%]
        S2[25%]
        S3[50%]
        S4[100%]
    end

    S1 -->|✓| S2 -->|✓| S3 -->|Current| S4
    
    style S1 fill:#4ade80
    style S2 fill:#4ade80
    style S3 fill:#3b82f6
    style S4 fill:#e5e7eb
```

Visual representation:
```
Step Progress: [===✓===][===✓===][===◉===][       ]
               10%      25%      50%      100%
                                 ↑
                            Current Step
```

#### Blue-Green Deployment Progress

```mermaid
graph LR
    subgraph "Blue Slot"
        B[Blue: v1.0.0<br/>Active ✓]
    end
    
    subgraph "Green Slot"
        G[Green: v2.0.0<br/>Standby]
    end
    
    subgraph "Traffic"
        T[100% → Blue]
    end
    
    T --> B
```

### Control Panel

Interactive controls for managing the deployment:

```
┌─────────────────────────────────────────────────────────────────┐
│  Deployment Controls                                            │
│                                                                  │
│  [▶️ Start]  [⏸️ Pause]  [▶️ Resume]  [↩️ Rollback]  [⏩ Promote] │
│                                                                  │
│  Reason (optional): [________________________]                  │
└─────────────────────────────────────────────────────────────────┘
```

| Control | Description | Available When |
|---------|-------------|----------------|
| Start | Begin deployment execution | Status: pending |
| Pause | Pause at current step | Status: in_progress |
| Resume | Continue from paused state | Status: paused |
| Rollback | Revert to previous version | Status: in_progress, paused |
| Promote | Skip to 100% immediately | Status: in_progress, paused (canary only) |
| Switch | Switch blue/green slots | Strategy: blue_green |

### Metrics Panel

Real-time metrics visualization:

```mermaid
graph TD
    subgraph "Metrics Dashboard"
        ER[Error Rate<br/>0.02%<br/>✓ < 5%]
        LT[Latency P99<br/>450ms<br/>✓ < 1000ms]
        SR[Success Rate<br/>99.8%<br/>✓ > 99%]
        RPS[Requests/sec<br/>1,234]
    end
```

#### Metric Cards

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Error Rate   │ │ Latency P99  │ │ Success Rate │ │ Requests/s   │
│              │ │              │ │              │ │              │
│   0.02%      │ │   450ms      │ │   99.8%      │ │   1,234      │
│   ✓ healthy  │ │   ✓ healthy  │ │   ✓ healthy  │ │              │
│ threshold:5% │ │ threshold:1s │ │ threshold:99%│ │              │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

### Event Log

Real-time event stream:

```
┌─────────────────────────────────────────────────────────────────┐
│  Event Log                                            [Filter ▾] │
├─────────────────────────────────────────────────────────────────┤
│  12:30:00  INFO   Traffic shifted to 50%                  system │
│  12:25:00  INFO   Metrics check passed                    system │
│  12:20:00  INFO   Traffic shifted to 25%                  system │
│  12:15:00  INFO   Metrics check passed                    system │
│  12:10:00  INFO   Traffic shifted to 10%                  system │
│  12:01:00  INFO   Deployment started                       admin │
│  12:00:00  INFO   Deployment created                       admin │
└─────────────────────────────────────────────────────────────────┘
```

### History Timeline

State change history:

```mermaid
graph TB
    subgraph "Timeline"
        T1[12:00 - Created by admin]
        T2[12:01 - Started]
        T3[12:10 - Traffic: 10%]
        T4[12:20 - Traffic: 25%]
        T5[12:30 - Traffic: 50%]
    end
    
    T1 --> T2 --> T3 --> T4 --> T5
```

---

## Creating Deployments

### Create Deployment Form

```mermaid
graph TD
    subgraph "Create Deployment"
        Step1[Select Service]
        Step2[Choose Strategy]
        Step3[Configure Options]
        Step4[Review & Create]
    end
    
    Step1 --> Step2 --> Step3 --> Step4
```

### Form Fields

#### Basic Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Service Name | Text/Select | Yes | Service to deploy |
| Target Version | Text | Yes | Version to deploy |
| Environment | Select | Yes | development, staging, production |
| Strategy | Select | Yes | canary or blue_green |

#### Canary Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Traffic Steps | Text | 10,25,50,100 | Comma-separated percentages |
| Auto-Start | Toggle | Off | Start immediately after creation |

#### Metrics Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| Error Rate | Number | 0.05 | Maximum acceptable error rate |
| Latency P99 | Number | 1000 | Maximum P99 latency (ms) |
| Success Rate | Number | 0.99 | Minimum success rate |

### Create Deployment Flow

```mermaid
sequenceDiagram
    participant User
    participant Form as Create Form
    participant API
    participant Engine as Orchestrator

    User->>Form: Fill form
    User->>Form: Click Create
    Form->>Form: Validate inputs
    Form->>API: POST /deployments
    API->>Engine: Create deployment
    Engine-->>API: Deployment created
    API-->>Form: Deployment response
    Form->>User: Redirect to detail view
    
    opt Auto-Start enabled
        Form->>API: POST /deployments/{id}/start
        API->>Engine: Start deployment
        Engine-->>API: Started
    end
```

---

## Real-Time Updates

### WebSocket Connection

The dashboard maintains a WebSocket connection for real-time updates:

```mermaid
sequenceDiagram
    participant Dashboard
    participant WS as WebSocket
    participant API
    participant Engine

    Dashboard->>WS: Connect with JWT
    WS-->>Dashboard: Connected
    Dashboard->>WS: Subscribe to deployment
    
    loop Real-time Updates
        Engine->>API: Event occurs
        API->>WS: Broadcast event
        WS-->>Dashboard: Push update
        Dashboard->>Dashboard: Update UI
    end
```

### Update Types

| Update Type | Description | UI Action |
|-------------|-------------|-----------|
| deployment_update | Status/traffic changed | Update status, progress |
| metrics_update | New metrics available | Update metrics cards |
| event | New event occurred | Add to event log |
| error | Error occurred | Show notification |

### Connection Status

The dashboard shows connection status:

| Status | Indicator | Description |
|--------|-----------|-------------|
| Connected | 🟢 | Real-time updates active |
| Connecting | 🟡 | Attempting to connect |
| Disconnected | 🔴 | No real-time updates |
| Reconnecting | 🟡 | Auto-reconnecting |

---

## Settings & Preferences

### User Settings

| Setting | Options | Description |
|---------|---------|-------------|
| Theme | Light/Dark/System | UI theme preference |
| Notifications | On/Off | Browser notifications |
| Auto-refresh | On/Off | Fallback when WS disconnected |
| Refresh Interval | 10-60s | Auto-refresh interval |

### Dashboard Preferences

| Setting | Options | Description |
|---------|---------|-------------|
| Default View | List/Grid | Preferred list layout |
| Items per Page | 10/25/50/100 | Pagination size |
| Default Environment | All/Dev/Staging/Prod | Default filter |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `g` + `d` | Go to Deployments |
| `g` + `c` | Go to Create |
| `r` | Refresh current view |
| `/` | Focus search |
| `Esc` | Close modal/cancel |
| `?` | Show keyboard shortcuts |

---

## Mobile Experience

The dashboard is responsive and works on mobile devices:

```
┌─────────────────────┐
│  ≡  ADO Dashboard   │
├─────────────────────┤
│                     │
│  Deployments        │
│  ─────────────────  │
│                     │
│  ┌───────────────┐  │
│  │ news-api      │  │
│  │ canary        │  │
│  │ ▓▓▓▓░░ 50%    │  │
│  │ in_progress   │  │
│  └───────────────┘  │
│                     │
│  ┌───────────────┐  │
│  │ auth-service  │  │
│  │ blue_green    │  │
│  │ ✓ completed   │  │
│  └───────────────┘  │
│                     │
│  [+] New Deployment │
└─────────────────────┘
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Can't login | Invalid credentials | Check username/password |
| No real-time updates | WebSocket disconnected | Check network, refresh page |
| Deployment not showing | Filter hiding it | Clear filters |
| Controls disabled | Insufficient permissions | Contact admin |
| Slow loading | Network issues | Check API connectivity |

### Connection Issues

```mermaid
graph TD
    A[Connection Issue] --> B{Type?}
    
    B -->|Login Failed| C[Check credentials]
    B -->|WebSocket Error| D[Check network]
    B -->|API Error| E[Check backend]
    
    C --> F[Reset password if needed]
    D --> G[Refresh page]
    E --> H[Check /health endpoint]
```

### Browser Compatibility

| Browser | Minimum Version | Status |
|---------|-----------------|--------|
| Chrome | 90+ | ✅ Full Support |
| Firefox | 88+ | ✅ Full Support |
| Safari | 14+ | ✅ Full Support |
| Edge | 90+ | ✅ Full Support |

### Performance Tips

1. **Use filters** - Reduce displayed deployments
2. **Close unused tabs** - Free up WebSocket connections
3. **Clear browser cache** - If UI behaves unexpectedly
4. **Check network** - Slow loading may indicate network issues

---

## Role-Based Views

### Admin View

Admins see all features:
- All deployments across environments
- User management section
- System configuration
- Audit logs

### Operator View

Operators see:
- Deployments they have access to
- Create/control deployments
- View metrics and events
- No user management

### Viewer View

Viewers see:
- Read-only deployment list
- View deployment details
- View metrics (read-only)
- No control actions

---

## Integration with Other Tools

### Opening from CLI

```bash
# Open dashboard for a specific deployment
adaptive-deploy status --deployment news-api-canary-20240101120000 --open-dashboard
```

### Linking from CI/CD

Include dashboard links in CI/CD notifications:

```yaml
# Example Slack notification
- name: Notify with Dashboard Link
  run: |
    DASHBOARD_URL="https://dashboard.example.com/deployments/${DEPLOYMENT_ID}"
    curl -X POST $SLACK_WEBHOOK -d "{
      \"text\": \"Deployment in progress\",
      \"attachments\": [{
        \"actions\": [{
          \"type\": \"button\",
          \"text\": \"View in Dashboard\",
          \"url\": \"${DASHBOARD_URL}\"
        }]
      }]
    }"
```

---

## See Also

- [API Reference](./API.md)
- [CLI Reference](./CLI.md)
- [Architecture Guide](./ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT.md)
