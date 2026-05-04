# MLSDM Deployment Guide

This directory contains deployment configurations (Kubernetes, Docker Compose, Grafana, Prometheus) for the MLSDM Governed Cognitive Memory system. "Production-ready" status is asserted by the upstream MLSDM project; the parent neosynaptex canon makes no such claim.

## Directory Structure

```
deploy/
├── README.md                    # This file
├── k8s/                         # Kubernetes manifests
│   ├── kustomization.yaml       # Kustomize configuration
│   ├── configmap.yaml           # Application configuration
│   ├── secrets.yaml             # Secrets template (DO NOT COMMIT REAL SECRETS)
│   ├── deployment.yaml          # Basic deployment
│   ├── production-deployment.yaml # Full production deployment with HA
│   ├── service.yaml             # Kubernetes Service
│   ├── ingress.yaml             # Ingress for external access
│   ├── network-policy.yaml      # Network security policies
│   └── service-monitor.yaml     # Prometheus Operator monitoring
├── docker/                      # Docker Compose configurations
│   ├── docker-compose.production.yaml  # Production docker-compose
│   ├── config/production.yaml   # Configuration for docker deployment
│   ├── monitoring/prometheus.yml # Prometheus configuration
│   └── grafana/provisioning/    # Grafana auto-provisioning
├── grafana/                     # Grafana dashboards
│   └── mlsdm_observability_dashboard.json
├── monitoring/                  # Monitoring configuration
│   ├── alertmanager-rules.yaml  # Prometheus alerting rules
│   └── grafana-dashboard.json   # SLO dashboard
└── scripts/                     # Deployment scripts
    └── validate-manifests.sh    # YAML validation script
```

## Deployment Options

### Option 1: Docker Compose (Recommended for Single Node)

```bash
# Navigate to deploy/docker directory
cd deploy/docker

# Create .env file with your configuration
cat > .env << EOF
API_KEY=your-secure-api-key
LLM_BACKEND=local_stub
LOG_LEVEL=INFO
EOF

# Start MLSDM API
docker-compose -f docker-compose.production.yaml up -d

# Start with monitoring (Prometheus + Grafana)
docker-compose -f docker-compose.production.yaml --profile monitoring up -d

# Check status
docker-compose -f docker-compose.production.yaml ps

# View logs
docker-compose -f docker-compose.production.yaml logs -f mlsdm-api
```

### Option 2: Kubernetes (Recommended for Production)

#### Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured with cluster access
- kustomize (optional, for kustomize deployments)
- Helm (optional, for ingress-nginx, cert-manager)

#### Basic Deployment

```bash
# Create namespace
kubectl create namespace mlsdm-production

# Apply all resources using kustomize
kubectl apply -k deploy/k8s/

# Or apply individual files
kubectl apply -f deploy/k8s/configmap.yaml -n mlsdm-production
kubectl apply -f deploy/k8s/secrets.yaml -n mlsdm-production
kubectl apply -f deploy/k8s/deployment.yaml -n mlsdm-production
kubectl apply -f deploy/k8s/service.yaml -n mlsdm-production
```

#### Production Deployment

For production with high availability:

```bash
# Create namespace
kubectl create namespace mlsdm-production

# Configure secrets (IMPORTANT: Use proper secret management)
kubectl create secret generic mlsdm-secrets \
  --from-literal=api-key='your-secure-api-key' \
  --from-literal=openai-api-key='sk-...' \
  -n mlsdm-production

# Apply production deployment
kubectl apply -f deploy/k8s/production-deployment.yaml

# Verify deployment
kubectl get pods -n mlsdm-production
kubectl get svc -n mlsdm-production
```

## Configuration

### Environment Variables

Key environment variables that can be configured:

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `config/production.yaml` | Path to configuration file |
| `API_KEY` | - | API authentication key |
| `LLM_BACKEND` | `local_stub` | LLM backend (`local_stub`, `openai`, `anthropic`) |
| `EMBEDDING_DIM` | `384` | Embedding dimension |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics |

### ConfigMap

Edit `deploy/k8s/configmap.yaml` to customize:

- Memory layer parameters
- Moral filter settings
- Cognitive rhythm configuration
- Observability settings

### Secrets Management

**⚠️ IMPORTANT**: Never commit real secrets to version control!

Recommended approaches:
1. **External Secrets Operator** - Sync from AWS Secrets Manager, Vault, etc.
2. **Sealed Secrets** - Encrypt secrets for Git storage
3. **Kubernetes secrets with CI/CD** - Create secrets during deployment

Example with External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: mlsdm-external-secrets
spec:
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: mlsdm-secrets
  data:
    - secretKey: api-key
      remoteRef:
        key: mlsdm/production/api-key
```

## Networking

### Ingress Setup

1. Install ingress controller:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
```

2. Install cert-manager for TLS:
```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set installCRDs=true
```

3. Update `deploy/k8s/ingress.yaml` with your domain
4. Apply ingress: `kubectl apply -f deploy/k8s/ingress.yaml -n mlsdm-production`

### Network Policies

Network policies implement zero-trust security:
- Default deny all ingress/egress
- Allow only necessary traffic flows
- Enable Prometheus scraping from monitoring namespace

Requires a CNI with NetworkPolicy support (Calico, Cilium, etc.)

## Monitoring

### Prometheus Integration

1. Install Prometheus Operator:
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
```

2. Apply ServiceMonitor:
```bash
kubectl apply -f deploy/k8s/service-monitor.yaml -n mlsdm-production
```

3. Apply alerting rules:
```bash
kubectl apply -f deploy/monitoring/alertmanager-rules.yaml -n monitoring
```

### Grafana Dashboards

Import dashboards into Grafana:

1. `deploy/grafana/mlsdm_observability_dashboard.json` - Main observability dashboard
2. `deploy/monitoring/grafana-dashboard.json` - SLO compliance dashboard

### Key Metrics

| Metric | Description | SLO Target |
|--------|-------------|------------|
| `mlsdm_requests_total` | Total requests by status | - |
| `mlsdm_processing_latency_milliseconds_bucket` | Request latency | P95 < 50ms |
| `mlsdm_events_processed_total` | Processed events | 1000+ RPS |
| `mlsdm_events_rejected_total` | Rejected events | - |
| `mlsdm_memory_usage_bytes` | Memory usage | ~29 MB |
| `mlsdm_moral_threshold` | Current moral threshold | 0.3-0.9 |

## Health Checks

### Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Simple health check | `{"status": "healthy"}` |
| `/health/liveness` | Kubernetes liveness probe | 200 OK |
| `/health/readiness` | Kubernetes readiness probe | 200 OK |
| `/health/detailed` | Detailed health status | Full system state |
| `/health/metrics` | Prometheus metrics | Text format |

### Verify Deployment

```bash
# Check pod health
kubectl get pods -n mlsdm-production

# Check service endpoints
kubectl get endpoints mlsdm-api -n mlsdm-production

# Test health endpoint
kubectl port-forward svc/mlsdm-api 8080:80 -n mlsdm-production &
curl http://localhost:8080/health

# View logs
kubectl logs -l app=mlsdm-api -n mlsdm-production --tail=100
```

## Scaling

### Horizontal Pod Autoscaler

The production deployment includes HPA configuration:

```yaml
minReplicas: 3
maxReplicas: 10
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 80
```

### Manual Scaling

```bash
# Scale deployment
kubectl scale deployment mlsdm-api --replicas=5 -n mlsdm-production

# Verify scaling
kubectl get pods -n mlsdm-production
```

## Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   kubectl describe pod <pod-name> -n mlsdm-production
   kubectl logs <pod-name> -n mlsdm-production
   ```

2. **Health check failing**
   ```bash
   kubectl exec -it <pod-name> -n mlsdm-production -- curl http://localhost:8000/health
   ```

3. **Network connectivity issues**
   ```bash
   kubectl run test-pod --rm -it --image=curlimages/curl -n mlsdm-production -- curl http://mlsdm-api/health
   ```

4. **Memory issues**
   ```bash
   kubectl top pods -n mlsdm-production
   ```

### Debug Mode

Enable debug logging:
```bash
kubectl set env deployment/mlsdm-api LOG_LEVEL=DEBUG -n mlsdm-production
```

## Rollback

```bash
# View rollout history
kubectl rollout history deployment/mlsdm-api -n mlsdm-production

# Rollback to previous version
kubectl rollout undo deployment/mlsdm-api -n mlsdm-production

# Rollback to specific revision
kubectl rollout undo deployment/mlsdm-api --to-revision=2 -n mlsdm-production
```

## Cleanup

```bash
# Delete all resources
kubectl delete -k deploy/k8s/

# Or delete namespace
kubectl delete namespace mlsdm-production
```

## Related Documentation

- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - Comprehensive deployment guide
- [CONFIGURATION_GUIDE.md](../CONFIGURATION_GUIDE.md) - Configuration reference
- [OBSERVABILITY_GUIDE.md](../OBSERVABILITY_GUIDE.md) - Monitoring setup
- [SECURITY_POLICY.md](../SECURITY_POLICY.md) - Security guidelines
- [RUNBOOK.md](../RUNBOOK.md) - Operational runbook
