# Catalog Service (QuickCart)
Owns products and stock. FastAPI + PostgreSQL. Port 8001.

## Run locally
    pip install -r requirements.txt
    uvicorn app.main:app --port 8001      # uses SQLite by default; Swagger at /docs

## Docker / Minikube
    minikube start
    eval $(minikube docker-env)           # PowerShell: minikube docker-env | Invoke-Expression
    docker build -t catalog-service:1.0 .
    kubectl apply -f k8s/catalog.yaml

## API
POST /products | PUT /products/{id} | GET /products | GET /products/{id}
POST /products/{id}/reserve | POST /products/{id}/release | GET /health
