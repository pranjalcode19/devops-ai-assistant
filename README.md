# devops-ai-assistant

A RAG-powered DevOps assistant that answers questions from internal runbooks, streams responses, runs live shell commands as an agent, and tracks confidence scores per answer.

## What it does

| Endpoint | Description |
|---|---|
| `POST /ask` | RAG answer from ingested docs + confidence score (1-10) |
| `POST /ask/stream` | Same but token-by-token streaming |
| `POST /agent` | LLM decides to run a shell command, observes output, answers |
| `GET /metrics` | Prometheus metrics (request count, latency) |
| `GET /health` | Health check for K8s probes |

## Architecture

```
Client
  └── POST /ask
        ├── ChromaDB (vector search) → retrieves relevant doc chunks
        ├── Ollama (llama3.2) → generates answer with doc context
        └── Ollama → confidence score (second LLM call)
```

## Run locally

**Prerequisites:** [Ollama](https://ollama.com) running with `llama3.2` pulled.

```bash
pip install -r requirements.txt

# Ingest docs into ChromaDB
python3 ingest.py

# Start the API
uvicorn server:app --reload --port 8000
```

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I restart a service?"}'
```

## Run with Docker

```bash
docker build -t devops-ai-assistant .
docker run -p 8000:8000 \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  devops-ai-assistant
```

## Run full stack (all 3 services + Prometheus + Grafana)

```bash
docker compose -f docker-compose.full.yml up --build
```

| Service | URL |
|---|---|
| devops-ai-assistant | http://localhost:8000 |
| llm-monitoring-dashboard | http://localhost:8001 |
| multi-agent-devops | http://localhost:8002 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin/admin) |

## Deploy to Kubernetes

```bash
# Apply namespace and base resources
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/

# Or via Helm (recommended)
helm upgrade --install devops-ai-assistant ./helm \
  -f helm/values/devops-ai-assistant.yaml \
  -n ai-platform --create-namespace \
  --set image.tag=<git-sha>

# Verify
helm test devops-ai-assistant -n ai-platform
```

## K8s architecture

```
Ingress (/)
  └── Service (ClusterIP :80)
        └── Deployment
              ├── initContainer: ingest.py (populates vectordb PVC once)
              └── Container: uvicorn server:app
                    └── PVC: /app/vectordb (ChromaDB persisted across restarts)
```

**Key design decisions:**
- `initContainer` runs `ingest.py` before the API starts — guarantees docs are ready
- `PVC` keeps ChromaDB data across pod restarts and redeployments
- `Secret` holds `OLLAMA_HOST` (not ConfigMap — secrets are RBAC-controlled)
- `maxUnavailable: 0` in rolling update — old pod stays until new pod passes readiness probe
- `PodDisruptionBudget` keeps minimum 1 pod up during node drains

## CI/CD

GitHub Actions pipeline on every push to `main`:

```
test → build-push (GHCR) → helm-lint → deploy → helm test
```

Image is tagged with the git SHA. Set `KUBECONFIG` as a base64-encoded repository secret to enable the deploy step.

## Adding new docs

Drop `.txt` files into `docs/` and re-run `ingest.py`. In K8s, trigger a pod restart — the initContainer re-ingests on next startup.
