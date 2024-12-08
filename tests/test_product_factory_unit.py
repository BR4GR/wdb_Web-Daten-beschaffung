import pytest
from src.models.product_factory import parse_quantity_price, calculate_unit_prices


@pytest.mark.parametrize(
    "quantity_price_str, expected",
    [
        # Valid inputs
        ("0.85/100g", (0.85, 100.0, "g")),
        ("1.20/100ml", (1.2, 100.0, "ml")),
        ("2.5/1l", (2.5, 1.0, "l")),
        ("3.0/500g", (3.0, 500.0, "g")),
        ("3.0 / 500g", (3.0, 500.0, "g")),  # with spaces
        ("3.5/50kg", (3.5, 50.0, "kg")),
        ("0.99/100l", (0.99, 100.0, "l")),
        ("1.00/100 gm", (1.0, 100, "gm")),  # space in unit not matching pattern
        # Invalid inputs (should return None, None, None)
        ("abc/100g", (None, None, None)),  # non-numeric price
        ("1/abcg", (None, None, None)),  # non-numeric price
        ("1.00", (None, None, None)),  # no slash
        ("/100g", (None, None, None)),  # no price before slash
        ("1.00/100", (None, None, None)),  # no unit after quantity
        (" ", (None, None, None)),  # empty-ish input
    ],
)
def test_parse_quantity_price(quantity_price_str, expected):
    """Test parsing of quantity price strings into (value, qty, unit)."""
    assert parse_quantity_price(quantity_price_str) == expected


@pytest.mark.parametrize(
    "offer_json, expected_normal, expected_promo",
    [
        # Case 1: promotionPrice.unitPrice is given - preferred source for promo price
        (
            {
                "price": {"value": 12.0},
                "promotionPrice": {
                    "value": 8.5,
                    "unitPrice": {"value": 0.85, "unit": "100g"},
                },
                "quantityPrice": "1.20/100g",
            },
            1.20,
            0.85,
        ),
        # Case 2: only promotionPrice (no unitPrice) & quantityPrice given
        # quantityPrice should reflect promo if promotion < price
        (
            {
                "price": {"value": 3},
                "promotionPrice": {"value": 1},
                "quantityPrice": "1.8/100g",
            },
            5.4,
            1.8,
        ),  # promo up known from quantityPrice
        # Case 3: no promotion, only quantityPrice
        (
            {"price": {"value": 2.2}, "quantityPrice": "2.2/100g"},
            2.2,
            None,
        ),  # normal unit price from quantityPrice
        # Case 4: Both price and promotionPrice with known promotion unit price from promotionPrice.unitPrice
        (
            {
                "price": {"value": 12},
                "promotionPrice": {
                    "value": 8.5,
                    "unitPrice": {"value": 0.85, "unit": "100g"},
                },
                "quantityPrice": "1.2/100g",
            },
            1.2,
            0.85,
        ),
        # Case 5: Invalid promotion unit info
        # If promotion unit info is invalid, we still try to return what we can
        (
            {
                "price": {"value": 10},
                "promotionPrice": {
                    "value": 5,
                    "unitPrice": {"value": 0.75, "unit": "abc"},
                },
                "quantityPrice": "2.0/100g",
            },
            1.5,
            0.75,
        ),
        # Case 6: Empty offer_json
        ({}, None, None),
        # Case 7: Only price, no quantity or promotion
        ({"price": {"value": 10}}, None, None),
        # Case 8: Only quantityPrice no price or promo
        # Can't determine if it's promo or not since no promotion data is given.
        # According to logic, it's normal_unit_price = None and promo = None
        # because we don't know if there's a promo and we can't derive total qty vs price.
        ({"quantityPrice": "3.0/100g"}, 3, None),
        # Case 9: Promotion price is equal to normal price, quantityPrice known
        # If promotion_price == price, there's no real promotion. So quantityPrice = normal price
        (
            {
                "price": {"value": 10.0},
                "promotionPrice": {"value": 5.0},
                "quantityPrice": "1.5/100g",
            },
            3,
            1.5,
        ),
    ],
)
def test_calculate_unit_prices(offer_json, expected_normal, expected_promo):
    """Test calculation of normal and promotion unit prices from offer JSON."""
    normal_up, promo_up = calculate_unit_prices(offer_json)

    # Use approx for floating-point comparisons where needed.
    if expected_normal is None:
        assert normal_up is None
    else:
        assert pytest.approx(normal_up, 0.001) == expected_normal

    if expected_promo is None:
        assert promo_up is None
    else:
        assert pytest.approx(promo_up, 0.001) == expected_promo
