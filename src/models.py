from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship

Base = declarative_base()

# Association table for many-to-many relationship between Product and Category (breadcrumb)
product_category_association = Table(
    "product_category",
    Base.metadata,
    Column("product_id", ForeignKey("products.id"), primary_key=True),
    Column("category_id", ForeignKey("categories.id"), primary_key=True),
)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    path = Column(String)
    level = Column(Integer)
    context = Column(String)
    products = relationship(
        "Product", secondary=product_category_association, back_populates="categories"
    )


class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    image_path = Column(String)


class Nutrients(Base):
    __tablename__ = "nutrients"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    energy_kcal = Column(Float)
    fat_g = Column(Float)
    saturates_g = Column(Float)
    carbohydrate_g = Column(Float)
    sugars_g = Column(Float)
    fibre_g = Column(Float)
    protein_g = Column(Float)
    salt_g = Column(Float)
    is_analytical_constituents = Column(Boolean, default=False)
    product = relationship("Product", back_populates="nutrients")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    migros_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"))
    brand = relationship("Brand", backref="products")
    versioning = Column(String)
    title = Column(String)
    description = Column(String)
    product_range = Column(String)
    product_availability = Column(String)
    origin = Column(String)
    ingredients = Column(String)
    co2_footprint_rating = Column(Integer)
    co2_kg_range = Column(String)
    rating_nb_reviews = Column(Integer)
    rating_nb_stars = Column(Float)
    migipedia_url = Column(String)
    legal_designation = Column(String)
    distributor_name = Column(String)
    distributor_address = Column(String)
    article_number = Column(String)
    usage = Column(String)
    additional_information = Column(String)
    pkg_quantity_g = Column(Float, nullable=True)
    pkg_quantity_ml = Column(Float, nullable=True)
    pkg_price = Column(Float)
    unit_100_price = Column(String)
    packaging_type = Column(String)
    storage_instructions = Column(String)
    washing_instructions = Column(String)
    product_url = Column(String)

    categories = relationship(
        "Category", secondary=product_category_association, back_populates="products"
    )
    images = relationship("ProductImage", backref="product")
    gtins = relationship("GTIN", backref="product")
    labels = relationship("ProductLabel", backref="product")
    pictos = relationship("ProductPicto", backref="product")
    nutrients = relationship("Nutrients", uselist=False, back_populates="product")
    prices = relationship("PriceHistory", back_populates="product")


class PriceHistory(Base):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    product = relationship("Product", back_populates="prices")
    price = Column(Float, nullable=False)
    date_scraped = Column(DateTime)


class ProductImage(Base):
    __tablename__ = "product_images"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))


class GTIN(Base):
    __tablename__ = "gtins"
    id = Column(Integer, primary_key=True)
    gtin = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))


class ProductLabel(Base):
    __tablename__ = "product_labels"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String)
    image_path = Column(String)
    product_id = Column(Integer, ForeignKey("products.id"))


class ProductPicto(Base):
    __tablename__ = "product_pictos"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    description = Column(String)
    image_path = Column(String)
    product_id = Column(Integer, ForeignKey("products.id"))
