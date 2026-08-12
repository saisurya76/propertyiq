import os


def test_payment_order_records_terms_and_property_payload(tmp_path, monkeypatch):
    database_path = tmp_path / "propertyiq_payments.db"
    monkeypatch.setenv("PROPERTYIQ_PAYMENT_DB_PATH", str(database_path))

    import backend.payment_store as payment_store

    payment_store.DEFAULT_DB_PATH = database_path
    payment_store.initialize_payment_store()
    payment_store.create_order(
        order_id="PIQ-test-order",
        property_payload={"country": "India", "propertyName": "Test Property"},
        terms_version="PropertyIQ Report Terms v1.0",
    )

    order = payment_store.get_order("PIQ-test-order")

    assert order is not None
    assert order["status"] == "pending_payment"
    assert order["currency"] == "INR"
    assert order["terms_version"] == "PropertyIQ Report Terms v1.0"
    assert order["terms_accepted_at"]
    assert order["property_payload"]["propertyName"] == "Test Property"
