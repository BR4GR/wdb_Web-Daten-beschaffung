def parse_nutrient_value(value_str: str) -> float:
    if value_str:
        return float("".join(filter(lambda x: x.isdigit() or x == ".", value_str)))
    return None
