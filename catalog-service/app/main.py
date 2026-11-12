import os
import time
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./catalog.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)


class ProductIn(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class StockChange(BaseModel):
    quantity: int = Field(gt=0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def to_dict(p: Product):
    return {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock}


app = FastAPI(title="Catalog Service", version="1.0.0")


@app.on_event("startup")
def init_db():
    # DB container may take a few seconds to come up in Kubernetes
    for _ in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("Database not reachable")


@app.get("/health")
def health():
    return {"status": "UP", "service": "catalog-service"}


# ---- Commands ----
@app.post("/products", status_code=201)
def create_product(body: ProductIn, db: Session = Depends(get_db)):
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return to_dict(p)


@app.put("/products/{pid}")
def update_product(pid: int, body: ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    p.name, p.price, p.stock = body.name, body.price, body.stock
    db.commit()
    return to_dict(p)


@app.post("/products/{pid}/reserve")
def reserve_stock(pid: int, body: StockChange, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == pid).with_for_update().first()
    if not p:
        raise HTTPException(404, "Product not found")
    if p.stock < body.quantity:
        raise HTTPException(409, f"Insufficient stock (available: {p.stock})")
    p.stock -= body.quantity
    db.commit()
    return to_dict(p)


@app.post("/products/{pid}/release")
def release_stock(pid: int, body: StockChange, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == pid).with_for_update().first()
    if not p:
        raise HTTPException(404, "Product not found")
    p.stock += body.quantity
    db.commit()
    return to_dict(p)


# ---- Queries ----
@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    return [to_dict(p) for p in db.query(Product).all()]


@app.get("/products/{pid}")
def get_product(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    return to_dict(p)
