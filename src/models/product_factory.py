import logging
import re
from datetime import datetime

from src.models.nutrition import Nutrition
from src.models.offer import Offer

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ProductFactory:
    @staticmethod
    def extract_number(quantity_str):
        """
        Extract a number from a string.
        If it is a float, return a float; if an int, return an int.
        If no number is found, return None.
        If it is already a number, return it as is.
        """
        if isinstance(quantity_str, (int, float)):
            return quantity_str

        match = re.search(r"(\d+(\.\d+)?)", quantity_str)
        if match:
            number_str = match.group(1)
            try:
                return float(number_str)
            except ValueError:
                logging.error(
                    f"Could not convert extracted number '{number_str}' to float."
                )
                return None
        return None

    @staticmethod
    def create_product_from_json(product_json):
        from src.models.product import Product

        nutrient_id = None
        offer_id = None
        nutrition = None
        offer = None

        # Extract nutrients
        nutrition = extract_nutrients(product_json)

        # Extract offer
        offer = extract_offer(product_json)

        # Extract product
        try:
            scraped_at_str = product_json.get("dateAdded")
            if scraped_at_str:
                try:
                    scraped_at = datetime.fromisoformat(scraped_at_str)
                except ValueError:
                    logging.warning(
                        f"Invalid date format for 'dateAdded': {scraped_at_str}"
                    )
                    scraped_at = datetime.now()
            else:
                scraped_at = datetime.now()

            gtins = product_json.get("gtins", [])
            gtins_str = ",".join(gtins) if isinstance(gtins, list) else gtins

            product = Product(
                migros_id=product_json.get("migrosId"),
                name=product_json.get("name"),
                brand=product_json.get("brand") or product_json.get("brandLine"),
                title=product_json.get("title"),
                description=product_json.get("description", None),
                ingredients=product_json.get("productInformation", {})
                .get("mainInformation", {})
                .get("ingredients", None),
                nutrition=nutrition,
                offer=offer,
                gtins=gtins_str,
                scraped_at=scraped_at,
            )
        except Exception as e:
            logging.error(f"Error processing product: {e}")

        return product


def extract_nutrients(product_json):
    try:
        nutrients_table = (
            product_json.get("productInformation", {})
            .get("nutrientsInformation", {})
            .get("nutrientsTable", None)
        )
        if not nutrients_table:
            return None

        headers = nutrients_table.get("headers", [])
        if not headers:
            return None

        unit_index = None
        unit = None
        quantity = None

        # Determine the correct column index for per 100g/ml values
        for i, header in enumerate(headers):
            if "100" in header:
                unit_index = i
                quantity = 100
                if "g" in header:
                    unit = "g"
                elif "ml" in header:
                    unit = "ml"
                break  # Stop after finding the correct header

            elif (
                "pill" in header
                or "capsule" in header
                or "drops" in header
                or "tablet" in header
                or "drop" in header
                or "sachet" in header
                or "ampule" in header
                or "stick" in header
            ):
                unit = header
                unit_index = i
                quantity = 1

            elif header == "1 l":
                unit = "ml"
                unit_index = i
                quantity = 1000

            else:
                print(f"Header: {header}")

        if unit_index is None:
            logging.warning("No suitable header found")
            return None
            # raise ValueError("Missing per 100g/ml header.")

        rows = nutrients_table.get("rows", [])
        nutrient_data = {
            "unit": unit,
            "quantity": quantity,
            "kcal": None,
            "kJ": None,
            "fat": None,
            "saturates": None,
            "carbohydrate": None,
            "sugars": None,
            "fibre": None,
            "protein": None,
            "salt": None,
        }

        for row in rows:
            label = row.get("label", "").lower()
            values = row.get("values", [])
            if len(values) > unit_index:
                value = values[unit_index]
                if "energy" in label:
                    # Extract kJ and kcal values
                    energy_match = re.search(
                        r"(\d+(\.\d+)?)\s*kJ.*?(\d+(\.\d+)?)\s*kcal",
                        value,
                        re.IGNORECASE,
                    )
                    if energy_match:
                        nutrient_data["kJ"] = float(energy_match.group(1))
                        nutrient_data["kcal"] = float(energy_match.group(3))
                    else:
                        logging.warning(f"Energy values not found in '{value}'.")
                else:
                    extracted_value = ProductFactory.extract_number(value)
                    if extracted_value is not None:
                        if "fat" in label and "saturates" not in label:
                            nutrient_data["fat"] = extracted_value
                        elif "saturates" in label:
                            nutrient_data["saturates"] = extracted_value
                        elif "carbohydrate" in label and "sugars" not in label:
                            nutrient_data["carbohydrate"] = extracted_value
                        elif "sugars" in label:
                            nutrient_data["sugars"] = extracted_value
                        elif "fibre" in label:
                            nutrient_data["fibre"] = extracted_value
                        elif "protein" in label:
                            nutrient_data["protein"] = extracted_value
                        elif "salt" in label:
                            nutrient_data["salt"] = extracted_value
                        else:
                            continue

        nutrition = Nutrition(**nutrient_data)
        return nutrition
    except Exception as e:
        logging.error(f"Error processing nutrients: {e}")
        return None


def extract_offer(product_json):
    offer_json = product_json.get("offer", {})
    try:
        if offer_json:
            offer_json = product_json.get("offer", {})
            price = offer_json.get("price", {}).get("value")
            quantity_str = offer_json.get("quantity")
            promotion_price = offer_json.get("promotionPrice", {}).get("value")

            normal_unit_price, promotion_unit_price = calculate_unit_prices(offer_json)

            offer = Offer(
                price=price,
                quantity=quantity_str,
                unit_price=normal_unit_price,
                promotion_price=promotion_price,
                promotion_unit_price=promotion_unit_price,
            )
            return offer
    except Exception as e:
        logging.error(f"Error processing offer: {e}")


def parse_quantity_price(quantity_price_str):
    """
    Parse a quantity price string like '0.85/100g' into a tuple (unit_price, unit_quantity, unit).
    For example:
    '0.85/100g' -> (0.85, 100, 'g')
    '1.20/100ml' -> (1.20, 100, 'ml')
    """
    if not quantity_price_str:
        return None, None, None
    # Remove all whitespace
    quantity_price_str = "".join(quantity_price_str.split())
    match = re.match(r"([\d\.]+)/(\d+)([a-zA-Z]+)$", quantity_price_str.strip())
    if not match:
        return None, None, None
    value_str, qty_str, unit_str = match.groups()
    try:
        value = float(value_str)
        qty = float(qty_str)
        return value, qty, unit_str
    except ValueError:
        logging.error(f"Error parsing quantity price from {quantity_price_str}")
        return None, None, None


def calculate_unit_prices(offer_json):
    """
    Determine normal_unit_price and promotion_unit_price using the best available data.
    Priority when a promotion is present:
      1. promotionPrice.unitPrice (directly use it)
      2. If missing, use quantityPrice (assume it reflects promotion price if promotion < price)
    If no promotion is present:
      - Use quantityPrice as normal unit price.
    """

    if not offer_json:
        return None, None

    price = offer_json.get("price", {}).get("value")
    promotion_price = offer_json.get("promotionPrice", {}).get("value")
    unit_info = offer_json.get("price", {}).get("unitPrice")
    promotion_unit_info = offer_json.get("promotionPrice", {}).get("unitPrice")
    quantity_price_str = offer_json.get("quantityPrice")  # e.g. "0.85/100g"

    normal_unit_price = None
    promotion_unit_price = None

    # Check if there is a promotion
    has_promotion = promotion_price is not None

    # If there's a promotion, try promotionPrice.unitPrice first
    if has_promotion and promotion_unit_info:
        promotion_unit_price = promotion_unit_info.get("value")
        if unit_info:
            return unit_info.get("value"), promotion_unit_price
        normal_unit_price = promotion_unit_price / promotion_price * price
        return normal_unit_price, promotion_unit_price

    if unit_info:
        return unit_info.get("value"), None

    q_val, q_qty, q_unit = parse_quantity_price(quantity_price_str)
    # if it is kg or l then convert to 100 g or ml
    if q_unit in ["kg", "l"]:
        q_qty *= 1000
        q_unit = "g" if q_unit == "kg" else "ml"

    # in case there are strange units like pill, return None None if unit is not g or ml
    if q_unit not in ["g", "ml"]:
        return None, None

    if has_promotion:
        promotion_unit_price = q_val / q_qty * 100
        normal_unit_price = promotion_unit_price / promotion_price * price
        return normal_unit_price, promotion_unit_price

    normal_unit_price = q_val / q_qty * 100

    return normal_unit_price, promotion_unit_price
