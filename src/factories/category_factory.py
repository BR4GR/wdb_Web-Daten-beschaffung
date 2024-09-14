from models import Category


class CategoryFactory:
    @staticmethod
    def create_category(data: dict) -> Category:
        return Category(
            id=data.get("id"),
            name=data.get("name"),
            slug=data.get("slug"),
            path=data.get("path"),
            level=data.get("level"),
            context=data.get("type"),
        )
