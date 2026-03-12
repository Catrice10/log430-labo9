"""
Distributed database concurrency test
SPDX-License-Identifier: LGPL-3.0-or-later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""


from db import Base
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Numeric,
    Boolean, ForeignKey, func
)
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(100), nullable=False)
    email      = Column(String(150), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"


class Product(Base):
    __tablename__ = "products"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(150), nullable=False)
    sku        = Column(String(64),  nullable=False, unique=True)
    price      = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock       = relationship("Stock",     back_populates="product", uselist=False)
    order_items = relationship("OrderItem", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}', price={self.price})>"


class Order(Base):
    __tablename__ = "orders"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    payment_link = Column(String(100), nullable=True)
    is_paid      = Column(Boolean, nullable=False, default=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    user  = relationship("User",      back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Order(id={self.id}, user_id={self.user_id}, "
            f"total={self.total_amount}, is_paid={self.is_paid})>"
        )


class OrderItem(Base):
    __tablename__ = "order_items"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    order_id   = Column(Integer, ForeignKey("orders.id",   ondelete="CASCADE"),  nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity   = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)

    order   = relationship("Order",   back_populates="items")
    product = relationship("Product", back_populates="order_items")

    def __repr__(self):
        return (
            f"<OrderItem(id={self.id}, order_id={self.order_id}, "
            f"product_id={self.product_id}, qty={self.quantity})>"
        )


class Stock(Base):
    __tablename__ = "stocks"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True)
    quantity   = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="stock")

    def __repr__(self):
        return f"<Stock(product_id={self.product_id}, quantity={self.quantity})>"
