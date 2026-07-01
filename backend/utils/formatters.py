def format_currency(value: float) -> str:
    return f"INR {value:,.0f}"

def format_price_per_sqft(value: float,
                          currency: str = "INR") -> str:
    return f"{currency} {value:,.0f} / sqft"    