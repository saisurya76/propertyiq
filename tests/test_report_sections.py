from backend.report_sections import (
    generate_fair_value_analysis,
    generate_methodology
)


def test_fair_value_analysis():

    result = generate_fair_value_analysis(
        quoted_price=18000000,
        fair_value=15840000
    )

    assert result["difference"] == 2160000

    assert result["premium_percent"] == 13.64


def test_methodology():

    result = generate_methodology()

    assert (
        result["fair_value_methodology"]
        ["Comparable Sales"]
        == "45%"
    )