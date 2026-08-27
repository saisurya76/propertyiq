import asyncio
from unittest.mock import patch

from backend.price_watch_scheduler import _run_one_check_cycle
from backend.price_watch_store import initialize_price_watch_store, create_price_watch, get_price_watch


def test_run_one_check_cycle_checks_all_active_url_watches():
    initialize_price_watch_store()
    watch1 = create_price_watch(
        email="cycle1@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/cycle1",
    )
    watch2 = create_price_watch(
        email="cycle2@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/cycle2",
    )
    manual_watch = create_price_watch(
        email="cycle3@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )

    with patch("backend.property_url_extract.extract_property_data", return_value={"quotedPrice": 8000000}), \
         patch("backend.auth.send_email"):
        asyncio.run(_run_one_check_cycle())

    assert get_price_watch(watch1["watch_id"])["status"] == "triggered"
    assert get_price_watch(watch2["watch_id"])["status"] == "triggered"
    assert get_price_watch(manual_watch["watch_id"])["last_checked_at"] is None


def test_one_watch_failing_does_not_stop_the_rest_of_the_batch():
    """A real, important guarantee: one broken/failing watch in a batch
    of many must not prevent the others from being checked."""
    initialize_price_watch_store()
    good_watch = create_price_watch(
        email="batchtest1@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/batch-good",
    )
    problem_watch = create_price_watch(
        email="batchtest2@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/batch-problem",
    )

    from backend.price_watch_store import check_price_watch as real_check

    def failing_check(watch_id, *args, **kwargs):
        if watch_id == problem_watch["watch_id"]:
            raise RuntimeError("simulated unexpected failure")
        return real_check(watch_id, *args, **kwargs)

    with patch("backend.price_watch_scheduler.check_price_watch", side_effect=failing_check), \
         patch("backend.property_url_extract.extract_property_data", return_value={"quotedPrice": 8000000}), \
         patch("backend.auth.send_email"):
        asyncio.run(_run_one_check_cycle())

    assert get_price_watch(good_watch["watch_id"])["status"] == "triggered"
