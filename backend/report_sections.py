def generate_property_snapshot(data):

    return {
        "property_name": data.property_name,
        "developer_name": data.developer_name,
        "location": f"{data.locality}, {data.city}",
        "property_type": data.property_type,
        "area": f"{data.unit_area} {data.area_unit}",
        "quoted_price": data.quoted_price,
        "currency": data.currency
    }


def generate_scorecard(
    buyer_protection_score,
    buyer_protection_rating,
    valuation_score,
    inventory_score,
    developer_score,
    recommendation
):

    return {
        "buyer_protection_score": buyer_protection_score,
        "buyer_protection_rating": buyer_protection_rating,
        "valuation_score": valuation_score,
        "inventory_score": inventory_score,
        "developer_score": developer_score,
        "recommendation": recommendation
    }


def generate_fair_value_analysis(
    quoted_price,
    fair_value
):

    difference = quoted_price - fair_value

    premium = round(
        (difference / fair_value) * 100,
        2
    )

    return {
        "quoted_price": quoted_price,
        "fair_value": fair_value,
        "difference": difference,
        "premium_percent": premium
    }


def generate_methodology():

    return {
        "fair_value_methodology": {
            "Comparable Sales": "45%",
            "Rental Yield": "25%",
            "Replacement Cost": "30%"
        },
        "buyer_protection_methodology": {
            "Valuation": "50%",
            "Inventory": "30%",
            "Developer": "20%"
        }
    }