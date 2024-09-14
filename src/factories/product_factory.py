from models import Brand, Nutrients, Product
from utils.parsing_utils import parse_nutrient_value


class ProductFactory:
    @staticmethod
    def create_product(data: dict) -> Product:
        brand = Brand(name=data.get("brand", "Unknown"))
        nutrients_data = data["productInformation"]["nutrientsInformation"][
            "nutrientsTable"
        ]["rows"]

        product = Product(
            migros_id=data["migrosId"],
            name=data["name"],
            brand=brand,
            versioning=data.get("versioning"),
            title=data.get("title"),
            description=data.get("description"),
            product_range=data.get("productRange"),
            product_availability=data.get("productAvailability"),
            origin=data["productInformation"]["mainInformation"].get("origin"),
            ingredients=data["productInformation"]["mainInformation"].get(
                "ingredients"
            ),
            co2_footprint_rating=data["productInformation"]["mainInformation"]
            .get("mcheck", {})
            .get("carbonFootprint", {})
            .get("rating"),
            co2_kg_range=data["productInformation"]["mainInformation"]
            .get("mcheck", {})
            .get("carbonFootprint", {})
            .get("co2KgRange"),
            rating_nb_reviews=data["productInformation"]["mainInformation"][
                "rating"
            ].get("nbReviews"),
            rating_nb_stars=data["productInformation"]["mainInformation"]["rating"].get(
                "nbStars"
            ),
            migipedia_url=data["productInformation"]["mainInformation"].get(
                "migipediaUrl"
            ),
            legal_designation=data["productInformation"]["otherInformation"].get(
                "legalDesignation"
            ),
            distributor_name=data["productInformation"]["otherInformation"].get(
                "distributorName"
            ),
            distributor_address=data["productInformation"]["otherInformation"].get(
                "distributorStreetAndNumber"
            ),
            article_number=data["productInformation"]["otherInformation"].get(
                "articleNumber"
            ),
            usage=data["productInformation"]["usageInformation"].get("usage"),
            additional_information=data["productInformation"]["usageInformation"].get(
                "additionalInformation"
            ),
            pkg_quantity_g=quantity_value if unit == "g" else None,
            pkg_quantity_ml=quantity_value if unit == "ml" else None,
            pkg_price=data["offer"]["price"]["value"],
            unit_100_price=f"{data['offer']['price']['unitPrice']['value']} {data['offer']['price']['unitPrice']['unit']}",
            packaging_type=data["productInformation"]["otherInformation"]
            .get("mainSpecificities", [{}])[0]
            .get("value"),
            storage_instructions=data["productInformation"]["otherInformation"]
            .get("mainSpecificities", [{}])[1]
            .get("value"),
            washing_instructions=data["productInformation"]["otherInformation"]
            .get("mainSpecificities", [{}])[2]
            .get("value"),
            product_url=data["productUrls"],
        )

        nutrients_info = Nutrients(
            energy_kcal=parse_nutrient_value(nutrients_data[0]["values"][0]),
            fat_g=parse_nutrient_value(nutrients_data[1]["values"][0]),
            saturates_g=parse_nutrient_value(nutrients_data[2]["values"][0]),
            carbohydrate_g=parse_nutrient_value(nutrients_data[3]["values"][0]),
            sugars_g=parse_nutrient_value(nutrients_data[4]["values"][0]),
            fibre_g=parse_nutrient_value(nutrients_data[5]["values"][0]),
            protein_g=parse_nutrient_value(nutrients_data[6]["values"][0]),
            salt_g=parse_nutrient_value(nutrients_data[7]["values"][0]),
            is_analytical_constituents=data["productInformation"][
                "nutrientsInformation"
            ].get("isAnalyticalConstituents", False),
        )
        product.nutrients = nutrients_info

        return product
