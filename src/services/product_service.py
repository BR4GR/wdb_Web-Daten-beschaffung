from factories.product_factory import ProductFactory
from models import Product
from sqlalchemy.orm import Session


class ProductService:
    def __init__(self, session: Session):
        self.session = session

    def create_product_from_data(self, data: dict) -> Product:
        product = ProductFactory.create_product(data)
        self.session.add(product)
        self.session.commit()
        return product
