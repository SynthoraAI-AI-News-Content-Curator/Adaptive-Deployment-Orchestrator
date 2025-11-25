# Security Best Practices

Comprehensive security guide for the Adaptive Deployment Orchestrator.

## Security Architecture

```mermaid
graph TB
    subgraph "External"
        User[Users]
        CI[CI/CD Systems]
    end

    subgraph "Edge Layer"
        WAF[Web Application Firewall]
        LB[Load Balancer]
        TLS[TLS Termination]
    end

    subgraph "Authentication"
        JWT[JWT Validation]
        RBAC[RBAC Engine]
        Audit[Audit Logger]
    end

    subgraph "Application"
        API[API Gateway]
        WS[WebSocket Server]
        Orchestrator[Orchestrator Engine]
    end

    subgraph "Data Layer"
        DB[(PostgreSQL)]
        Secrets[Secrets Manager]
    end

    User --> WAF
    CI --> WAF
    WAF --> LB
    LB --> TLS
    TLS --> JWT

    JWT --> RBAC
    RBAC --> API
    RBAC --> WS
    RBAC --> Audit

    API --> Orchestrator
    Orchestrator --> DB
    Orchestrator --> Secrets
```

---

## Authentication

### JWT Token Authentication

The system uses JSON Web Tokens (JWT) for stateless authentication.

```mermaid
sequenceDiagram
    participant User
    participant API as API Gateway
    participant Auth as Auth Service
    participant DB as Database

    User->>API: POST /auth/login (credentials)
    API->>Auth: Validate credentials
    Auth->>DB: Query user
    DB-->>Auth: User data + hashed password
    Auth->>Auth: Verify password (bcrypt)
    Auth->>Auth: Generate JWT (HS256)
    Auth-->>API: JWT Token
    API-->>User: { access_token: "...", expires_in: 3600 }

    Note over User,API: Subsequent requests

    User->>API: Request with Bearer token
    API->>Auth: Validate JWT
    Auth->>Auth: Verify signature & expiry
    Auth-->>API: Token valid + claims
    API-->>User: Response
```

### Token Configuration

| Setting | Default | Recommended | Description |
|---------|---------|-------------|-------------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | 15-60 | Token expiration time |
| `ALGORITHM` | HS256 | RS256 | Signing algorithm |
| `SECRET_KEY` | None | 32+ chars | Signing key |

### Production Configuration

```bash
# Generate a secure secret key (256 bits of entropy)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Set environment variable
export SECRET_KEY="your-64-character-secure-random-string-here-change-this"
```

**Best Practices:**

1. Use 64+ character random secret keys
2. Rotate secrets periodically (quarterly recommended)
3. Never commit secrets to source control
4. Use secrets management (AWS Secrets Manager, HashiCorp Vault)
5. Consider RS256 for microservices architectures

---

## Authorization (RBAC)

### Role-Based Access Control

```mermaid
graph TD
    subgraph "Roles"
        Admin[Admin]
        Operator[Operator]
        Viewer[Viewer]
    end

    subgraph "Permissions"
        DC[deployments:create]
        DR[deployments:read]
        DU[deployments:update]
        DD[deployments:delete]
        DCT[deployments:control]
        UC[users:create]
        UR[users:read]
        UU[users:update]
        UD[users:delete]
        AR[audit:read]
    end

    Admin --> DC & DR & DU & DD & DCT
    Admin --> UC & UR & UU & UD & AR

    Operator --> DC & DR & DU & DCT & AR

    Viewer --> DR & AR
```

### Permission Matrix

| Permission | Admin | Operator | Viewer |
|------------|:-----:|:--------:|:------:|
| deployments:create | ✅ | ✅ | ❌ |
| deployments:read | ✅ | ✅ | ✅ |
| deployments:update | ✅ | ✅ | ❌ |
| deployments:delete | ✅ | ❌ | ❌ |
| deployments:control | ✅ | ✅ | ❌ |
| users:create | ✅ | ❌ | ❌ |
| users:read | ✅ | ❌ | ❌ |
| users:update | ✅ | ❌ | ❌ |
| users:delete | ✅ | ❌ | ❌ |
| audit:read | ✅ | ✅ | ✅ |

### Role Assignment Best Practices

```
Production Team Structure:
├── Platform Admins (admin role)
│   └── Full system access, user management
├── DevOps Engineers (operator role)
│   └── Deploy and manage applications
├── Developers (operator role)
│   └── Deploy to staging/development
└── Stakeholders (viewer role)
    └── View deployment status only
```

**Recommendations:**

1. Principle of least privilege - assign minimum required permissions
2. Review role assignments quarterly
3. Use separate accounts for different environments
4. Log all permission changes

---

## Password Security

### Password Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Length | 8 characters | 12+ characters |
| Complexity | Letters + numbers | Mixed case + numbers + symbols |
| History | N/A | Prevent last 5 passwords |
| Expiry | N/A | 90 days for sensitive roles |

### Password Hashing

```python
# bcrypt hashing with default cost factor
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password
hashed = pwd_context.hash("user_password")

# Verify password
is_valid = pwd_context.verify("user_password", hashed)
```

### Default Password Change

**Critical:** Change default admin password immediately after installation!

```bash
# Change admin password via API
curl -X POST http://localhost:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "<your-current-password>",
    "new_password": "<your-secure-new-password>"
  }'
```

---

## Network Security

### TLS/SSL Configuration

```mermaid
graph LR
    subgraph "Internet"
        Client[Client]
    end

    subgraph "Edge"
        LB[Load Balancer<br/>TLS 1.3]
    end

    subgraph "Internal Network"
        API[API Server]
        DB[(Database)]
    end

    Client -->|HTTPS| LB
    LB -->|HTTP/2| API
    API -->|TLS| DB
```

### Nginx SSL Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    # SSL/TLS Configuration
    ssl_certificate /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;
    
    # Modern TLS configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # Additional security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'" always;

    location / {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

### Database SSL

```bash
# PostgreSQL SSL connection
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require

# With client certificates
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=verify-full&sslrootcert=/path/to/ca.crt
```

### Network Segmentation

```
┌─────────────────────────────────────────────────────────┐
│ Public Network (Internet)                               │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS (443)
┌──────────────────────▼──────────────────────────────────┐
│ DMZ (Load Balancer / WAF)                               │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (8000)
┌──────────────────────▼──────────────────────────────────┐
│ Application Network                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   API       │  │  Frontend   │  │  Worker     │      │
│  │   Server    │  │   Server    │  │  Services   │      │
│  └──────┬──────┘  └─────────────┘  └──────┬──────┘      │
│         │                                  │             │
└─────────┼──────────────────────────────────┼────────────┘
          │ PostgreSQL (5432)                │
┌─────────▼──────────────────────────────────▼────────────┐
│ Data Network                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  PostgreSQL │  │   Redis     │  │ Prometheus  │      │
│  │  Database   │  │   Cache     │  │  Metrics    │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

**Firewall Rules:**

| Source | Destination | Port | Protocol | Action |
|--------|-------------|------|----------|--------|
| Internet | Load Balancer | 443 | HTTPS | Allow |
| Load Balancer | API Server | 8000 | HTTP | Allow |
| API Server | Database | 5432 | PostgreSQL | Allow |
| API Server | Prometheus | 9090 | HTTP | Allow |
| All | All | * | * | Deny |

---

## CORS Configuration

### Production Settings

```python
# backend/app/core/config.py
CORS_ORIGINS = [
    "https://dashboard.example.com",
    "https://admin.example.com"
]
```

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)
```

**Best Practices:**

1. Never use `*` for origins in production
2. Explicitly list allowed origins
3. Minimize allowed methods and headers
4. Set appropriate max_age for preflight caching

---

## Input Validation

### Request Validation

```python
from pydantic import BaseModel, Field, validator

class DeploymentCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=200)
    environment: EnvironmentEnum
    strategy: DeploymentStrategyEnum
    target_version: str = Field(..., min_length=1, max_length=100)
    
    @validator('service_name')
    def validate_service_name(cls, v):
        # Only allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Invalid characters in service name')
        return v
```

### SQL Injection Prevention

```python
# Use parameterized queries with SQLAlchemy
from sqlalchemy import select

# Safe - parameterized query
query = select(Deployment).where(Deployment.service_name == service_name)

# Never do this - vulnerable to SQL injection
# query = f"SELECT * FROM deployments WHERE service_name = '{service_name}'"
```

### XSS Prevention

```python
# Escape HTML in responses
from markupsafe import escape

def format_message(message: str) -> str:
    return escape(message)
```

---

## Audit Logging

### Audit Events

```mermaid
graph LR
    subgraph "Actions"
        Login[Login]
        Deploy[Deployment]
        Control[Control Actions]
        Admin[Admin Actions]
    end

    subgraph "Audit Log"
        AL[(Audit Log DB)]
    end

    subgraph "Outputs"
        SIEM[SIEM]
        Alert[Alerts]
        Report[Reports]
    end

    Login --> AL
    Deploy --> AL
    Control --> AL
    Admin --> AL

    AL --> SIEM
    AL --> Alert
    AL --> Report
```

### Logged Events

| Event | Severity | Data Captured |
|-------|----------|---------------|
| Login Success | INFO | Username, IP, User-Agent |
| Login Failure | WARNING | Username, IP, Reason |
| Deployment Created | INFO | Deployment details, Creator |
| Deployment Started | INFO | Deployment ID, Operator |
| Deployment Paused | INFO | Deployment ID, Reason, Operator |
| Deployment Rollback | WARNING | Deployment ID, Reason, Operator |
| User Created | INFO | Username, Role, Creator |
| User Deleted | WARNING | Username, Deletor |
| Permission Changed | WARNING | User, Old/New Role, Admin |

### Audit Log Schema

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(200),
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    request_data JSONB,
    response_data JSONB
);

CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
```

### Log Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Security Logs | 1 year | Immutable storage |
| Audit Logs | 2 years | Encrypted storage |
| Access Logs | 90 days | Standard storage |
| Error Logs | 30 days | Standard storage |

---

## Secrets Management

### Environment Variables

```bash
# Required secrets (must be set in production)
SECRET_KEY=<64-char-random-string>
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db

# Optional secrets
PROMETHEUS_URL=http://prometheus:9090
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Using Secrets Managers

#### AWS Secrets Manager

```python
import boto3
import json

def get_secret(secret_name: str) -> dict:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
secrets = get_secret('prod/ado/database')
DATABASE_URL = secrets['url']
```

#### HashiCorp Vault

```python
import hvac

client = hvac.Client(url='https://vault.example.com:8200')
client.token = os.environ['VAULT_TOKEN']

secret = client.secrets.kv.read_secret_version(path='ado/database')
DATABASE_URL = secret['data']['data']['url']
```

#### Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ado-secrets
type: Opaque
data:
  secret-key: <base64-encoded-secret>
  database-url: <base64-encoded-url>
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: api
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: ado-secrets
              key: secret-key
```

---

## Security Checklist

### Before Production

```markdown
## Authentication & Authorization
- [ ] Changed default admin password
- [ ] Generated secure SECRET_KEY (64+ chars)
- [ ] Reviewed RBAC role assignments
- [ ] Tested permission boundaries

## Network Security
- [ ] TLS/SSL enabled (TLS 1.2+)
- [ ] HSTS header configured
- [ ] Security headers configured
- [ ] CORS origins restricted
- [ ] Database SSL enabled

## Infrastructure
- [ ] Firewall rules configured
- [ ] Network segmentation implemented
- [ ] Database in private network
- [ ] Secrets in secrets manager

## Monitoring & Audit
- [ ] Audit logging enabled
- [ ] Security alerts configured
- [ ] Log aggregation set up
- [ ] Incident response plan documented

## Application Security
- [ ] Input validation enabled
- [ ] SQL injection protected (ORM)
- [ ] Rate limiting configured
- [ ] Error messages sanitized
```

### Regular Security Tasks

| Frequency | Task |
|-----------|------|
| Daily | Review security alerts |
| Weekly | Check audit logs for anomalies |
| Monthly | Review access permissions |
| Quarterly | Rotate secrets and keys |
| Quarterly | Security assessment/penetration testing |
| Annually | Full security audit |

---

## Incident Response

### Security Incident Flow

```mermaid
graph TD
    A[Incident Detected] --> B{Severity?}
    
    B -->|Critical| C[Immediate Response]
    B -->|High| D[1-Hour Response]
    B -->|Medium| E[24-Hour Response]
    B -->|Low| F[Next Business Day]
    
    C --> G[Isolate System]
    G --> H[Preserve Evidence]
    H --> I[Investigate]
    I --> J[Remediate]
    J --> K[Post-Mortem]
    
    D --> I
    E --> I
    F --> I
```

### Incident Severity Levels

| Level | Examples | Response Time |
|-------|----------|---------------|
| Critical | Data breach, System compromise | Immediate |
| High | Authentication bypass, Privilege escalation | 1 hour |
| Medium | Suspicious access patterns | 24 hours |
| Low | Failed login attempts | Next business day |

### Contact Information

```yaml
# Security Contacts (customize for your organization)
security_team:
  email: security@example.com
  slack: #security-incidents
  pagerduty: security-oncall

escalation:
  - level: 1
    contact: On-call Engineer
    time: 15 minutes
  - level: 2
    contact: Security Lead
    time: 30 minutes
  - level: 3
    contact: CTO
    time: 1 hour
```

---

## Compliance

### Supported Standards

- **SOC 2**: Audit logging, access controls, encryption
- **GDPR**: Data protection, audit trails, access rights
- **HIPAA**: Encryption, access controls, audit logs
- **PCI DSS**: Network segmentation, encryption, logging

### Data Protection

```mermaid
graph TD
    subgraph "Data Classification"
        Public[Public Data]
        Internal[Internal Data]
        Confidential[Confidential Data]
        Restricted[Restricted Data]
    end

    subgraph "Protection Controls"
        Encrypt[Encryption]
        Access[Access Control]
        Audit[Audit Logging]
        Mask[Data Masking]
    end

    Confidential --> Encrypt
    Confidential --> Access
    Confidential --> Audit

    Restricted --> Encrypt
    Restricted --> Access
    Restricted --> Audit
    Restricted --> Mask
```

---

## Security Updates

### Dependency Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  push:
    branches: [main]

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Python Security Scan
        run: |
          pip install safety
          safety check -r backend/requirements.txt
          
      - name: Node.js Security Scan
        run: |
          cd frontend
          npm audit --audit-level=high
          
      - name: Container Scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'ado-backend:latest'
          severity: 'CRITICAL,HIGH'
```

### Vulnerability Response

| Severity | Response Time | Action |
|----------|---------------|--------|
| Critical | 24 hours | Immediate patch |
| High | 7 days | Priority patch |
| Medium | 30 days | Scheduled patch |
| Low | 90 days | Next release |

---

## See Also

- [Architecture Guide](./ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [API Reference](./API.md)
- [CI/CD Integration](./CICD.md)
