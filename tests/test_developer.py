from backend.developer import (
    assess_developer
)


def test_excellent_developer():

    result = assess_developer(
        projects_completed=20,
        projects_delayed=1,
        years_in_business=20,
        rera_violations=0
    )

    assert result.rating == "EXCELLENT"