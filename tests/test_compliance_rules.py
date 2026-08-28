from backend.compliance_rules import get_vastu_rules, get_thai_rules
from backend.construction_studio import VASTU_FAVORABLE_ENTRANCES, VASTU_UNFAVORABLE_SLOPES
from backend.vastu_engine import ROOM_PLACEMENT_RULES
from backend.thai_traditional_engine import THAI_FAVORABLE_ENTRANCES, THAI_UNFAVORABLE_ENTRANCES, THAI_ADJACENCY_RULES


def test_vastu_rules_returns_correct_structure():
    result = get_vastu_rules()
    assert result["tradition"] == "vastu"
    assert len(result["rules"]) > 0
    for rule in result["rules"]:
        assert rule["category"]
        assert rule["title"]
        assert rule["detail"]
    assert "astrological" in result["scope_note"]


def test_vastu_rules_count_matches_the_real_room_placement_rules_plus_fixed_entries():
    """A genuine anti-drift guard: if someone adds a new room-placement
    rule to vastu_engine.py, this popup must automatically pick it up —
    confirmed here by checking the count tracks the real rule list, not
    a hardcoded number that could silently go stale."""
    result = get_vastu_rules()
    # 3 fixed entries (entrance, slope, Brahmasthan) + one per real room-placement rule
    assert len(result["rules"]) == 3 + len(ROOM_PLACEMENT_RULES)


def test_vastu_rules_entrance_text_reflects_the_real_favorable_set():
    """If VASTU_FAVORABLE_ENTRANCES ever changes, this text must change
    with it automatically -- not silently describe a stale set."""
    result = get_vastu_rules()
    entrance_rule = next(r for r in result["rules"] if r["title"] == "Favorable entrance directions")
    for direction in VASTU_FAVORABLE_ENTRANCES:
        assert direction.title() in entrance_rule["detail"]


def test_vastu_rules_slope_text_reflects_the_real_unfavorable_set():
    result = get_vastu_rules()
    slope_rule = next(r for r in result["rules"] if r["title"] == "Unfavorable slope directions")
    for direction in VASTU_UNFAVORABLE_SLOPES:
        assert direction.title() in slope_rule["detail"]


def test_thai_rules_returns_correct_structure():
    result = get_thai_rules()
    assert result["tradition"] == "thai"
    assert len(result["rules"]) > 0
    for rule in result["rules"]:
        assert rule["category"]
        assert rule["title"]
        assert rule["detail"]
    assert "astrological" in result["scope_note"]


def test_thai_rules_count_matches_the_real_adjacency_rules_plus_fixed_entries():
    result = get_thai_rules()
    # 2 fixed entries (favorable/unfavorable orientation) + one per real adjacency rule
    assert len(result["rules"]) == 2 + len(THAI_ADJACENCY_RULES)


def test_thai_rules_orientation_text_reflects_the_real_sets():
    result = get_thai_rules()
    favorable_rule = next(r for r in result["rules"] if "Favorable entrance" in r["title"])
    for direction in THAI_FAVORABLE_ENTRANCES:
        assert direction.title() in favorable_rule["detail"]

    unfavorable_rule = next(r for r in result["rules"] if "Discouraged" in r["title"])
    for direction in THAI_UNFAVORABLE_ENTRANCES:
        assert direction.title() in unfavorable_rule["detail"]


def test_thai_adjacency_rules_are_all_represented():
    result = get_thai_rules()
    adjacency_titles = {r["title"] for r in result["rules"] if r["category"] == "Room Adjacency"}
    for type_a, type_b, _, _ in THAI_ADJACENCY_RULES:
        assert f"{type_a.title()} and {type_b.title()}" in adjacency_titles


def test_endpoint_returns_vastu_rules_publicly():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/construction-studio/compliance-rules?tradition=vastu")
    assert r.status_code == 200
    assert r.json()["tradition"] == "vastu"
    assert len(r.json()["rules"]) > 0


def test_endpoint_returns_thai_rules_publicly():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/construction-studio/compliance-rules?tradition=thai")
    assert r.status_code == 200
    assert r.json()["tradition"] == "thai"
    assert len(r.json()["rules"]) > 0


def test_endpoint_rejects_invalid_tradition():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/construction-studio/compliance-rules?tradition=feng_shui")
    assert r.status_code == 400
