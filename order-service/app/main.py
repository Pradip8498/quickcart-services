import os
import time
from datetime import datetime
import httpx
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String(100), nullable=False)
    product_id = Column(Integer, nullable=False)
    product_name = Column(String(100))
    quantity = Column(Integer, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(String(20), default="CONFIRMED")
    created_at = Column(DateTime, default=datetime.utcnow)


class OrderIn(BaseModel):
    customer: str = Field(min_length=1)
    product_id: int
    quantity: int = Field(gt=0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_dict(o: Order):
    return {
        "id": o.id, "customer": o.customer, "product_id": o.product_id,
        "product_name": o.product_name, "quantity": o.quantity,
        "total": o.total, "status": o.status, "created_at": o.created_at.isoformat(),
    }


app = FastAPI(title="Order Service", version="1.0.0")


@app.on_event("startup")
def init_db():
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("Database not reachable")


@app.get("/health")
def health():
    return {"status": "UP", "service": "order-service"}


def catalog_call(method: str, path: str, **kwargs):
    try:
        return httpx.request(method, f"{CATALOG_URL}{path}", timeout=5.0, **kwargs)
    except httpx.RequestError:
        raise HTTPException(503, "Catalog service unavailable")


# ---- Command: place order (synchronous REST call to Catalog Service) ----
@app.post("/orders", status_code=201)
def place_order(body: OrderIn, db: Session = Depends(get_db)):
    r = catalog_call("GET", f"/products/{body.product_id}")
    if r.status_code == 404:
        raise HTTPException(404, "Product does not exist")
    product = r.json()

    r = catalog_call("POST", f"/products/{body.product_id}/reserve",
                     json={"quantity": body.quantity})
    if r.status_code == 409:
        raise HTTPException(409, r.json().get("detail", "Insufficient stock"))
    if r.status_code != 200:
        raise HTTPException(502, "Could not reserve stock")

    try:
        order = Order(customer=body.customer, product_id=body.product_id,
                      product_name=product["name"], quantity=body.quantity,
                      total=round(product["price"] * body.quantity, 2))
        db.add(order)
        db.commit()
        db.refresh(order)
    except Exception:
        # compensating action: give the stock back
        catalog_call("POST", f"/products/{body.product_id}/release",
                     json={"quantity": body.quantity})
        raise HTTPException(500, "Order could not be saved; stock released")
    return to_dict(order)


# ---- Command: cancel order ----
@app.post("/orders/{oid}/cancel")
def cancel_order(oid: int, db: Session = Depends(get_db)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    if o.status == "CANCELLED":
        raise HTTPException(409, "Order already cancelled")
    catalog_call("POST", f"/products/{o.product_id}/release", json={"quantity": o.quantity})
    o.status = "CANCELLED"
    db.commit()
    return to_dict(o)


# ---- Queries ----
@app.get("/orders")
def list_orders(customer: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Order)
    if customer:
        q = q.filter(Order.customer == customer)
    return [to_dict(o) for o in q.all()]


@app.get("/orders/{oid}")
def get_order(oid: int, db: Session = Depends(get_db)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    return to_dict(o)
