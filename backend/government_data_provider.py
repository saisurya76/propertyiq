import json
from pathlib import Path


def _find_key(mapping, value):
    for key in mapping:
        if key.lower() == value.strip().lower():
            return key

    raise KeyError(value)


def get_government_rate(
    country: str,
    state_province: str,
    city: str,
    property_type: str
) -> float:

    data_file = (
        Path(__file__).parent.parent
        / "data"
        / "government"
        / "india.json"
    )

    with open(data_file, "r") as f:
        data = json.load(f)

    state_key = _find_key(
        data,
        state_province
    )

    city_key = _find_key(
        data[state_key],
        city
    )

    property_key = _find_key(
        data[state_key][city_key],
        property_type
    )

    return data[
        state_key
    ][
        city_key
    ][
        property_key
    ][
        "government_rate"
    ]