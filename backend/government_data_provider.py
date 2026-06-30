import json
from pathlib import Path

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

    return data[
        state_province
    ][
        city
    ][
        property_type
    ][
        "government_rate"
    ]