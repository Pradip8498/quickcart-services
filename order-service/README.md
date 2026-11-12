# Order Service (QuickCart)
Owns orders. Calls Catalog Service over REST to reserve stock. FastAPI + PostgreSQL. Port 8002.

## Run locally
    pip install -r requirements.txt
    CATALOG_URL=http://localhost:8001 uvicorn app.main:app --port 8002

## Docker / Minikube
    eval $(minikube docker-env)
    docker build -t order-service:1.0 .
    kubectl apply -f k8s/order.yaml

## API
POST /orders | POST /orders/{id}/cancel | GET /orders?customer= | GET /orders/{id} | GET /health
