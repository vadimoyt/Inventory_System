import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database import Base


class Manufacturer(Base):

    __tablename__ = "manufacturer"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    manager = Column(String(100))

    products = relationship("Product", back_populates="manufacturer")

    def __repr__(self):
        return f"<Manufacturer(id={self.id}, name={self.name})>"


class Counterparty(Base):

    __tablename__ = "counterparty"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)

    products = relationship("Product", back_populates="counterparty")
    agreements = relationship("Agreement", back_populates="counterparty")

    def __repr__(self):
        return f"<Counterparty(id={self.id}, name={self.name})>"


class Agreement(Base):

    __tablename__ = "agreement"

    id = Column(Integer, primary_key=True)
    contract_number = Column(String(50), unique=True, nullable=False)
    date_signed = Column(DateTime, nullable=False)
    counterparty_id = Column(Integer, ForeignKey("counterparty.id"), nullable=False)

    counterparty = relationship("Counterparty", back_populates="agreements")
    products = relationship("Product", back_populates="agreement")

    def __repr__(self):
        return f"<Agreement(id={self.id}, contract_number={self.contract_number})>"


class Product(Base):

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    price = Column(Float, nullable=False)
    manufacturer_id = Column(Integer, ForeignKey("manufacturer.id"), nullable=False)
    counterparty_id = Column(Integer, ForeignKey("counterparty.id"), nullable=False)
    agreement_id = Column(Integer, ForeignKey("agreement.id"), nullable=False)

    manufacturer = relationship("Manufacturer", back_populates="products")
    counterparty = relationship("Counterparty", back_populates="products")
    agreement = relationship("Agreement", back_populates="products")

    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, price={self.price})>"


class Sale(Base):

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    date_sold = Column(DateTime, default=datetime.datetime.utcnow)

    product = relationship("Product")

    def __repr__(self):
        return f"<Sale(id={self.id}, product_id={self.product_id}, quantity={self.quantity}, total_price={self.total_price})>"


class Stock(Base):

    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)

    product = relationship("Product")

    def __repr__(self):
        return f"<Stock(id={self.id}, product_id={self.product_id}, quantity={self.quantity})>"