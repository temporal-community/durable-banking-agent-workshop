from __future__ import annotations


def test_get_account_returns_seeded_balance(client):
    res = client.get("/accounts/A")
    assert res.status_code == 200
    body = res.json()
    assert body["balance"] == 5000.0
    assert body["home_country"] == "United States"

    res = client.get("/accounts/B")
    assert res.status_code == 200
    assert res.json()["balance"] == 3000.0


def test_get_unknown_account_is_404(client):
    res = client.get("/accounts/nonexistent")
    assert res.status_code == 404


def test_transfer_unknown_from_account_is_404(client):
    res = client.post(
        "/transfer",
        json={"from_account": "Z", "to_account": "B", "amount": 10, "spoof_location": "New York"},
    )
    assert res.status_code == 404


def test_transfer_unknown_to_account_is_404(client):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "Z", "amount": 10, "spoof_location": "New York"},
    )
    assert res.status_code == 404


def test_transfer_zero_amount_is_400(client):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 0, "spoof_location": "New York"},
    )
    assert res.status_code == 400


def test_transfer_negative_amount_is_400(client):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": -50, "spoof_location": "New York"},
    )
    assert res.status_code == 400


def test_transfer_exceeding_balance_is_400(client):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 999_999, "spoof_location": "New York"},
    )
    assert res.status_code == 400
    assert "insufficient" in res.json()["detail"].lower()


def test_transfer_unknown_spoof_location_is_400(client):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 10, "spoof_location": "Atlantis"},
    )
    assert res.status_code == 400
    assert "unknown spoof location" in res.json()["detail"].lower()


def test_approved_transfer_updates_balances_and_location(client, mock_geo_success, mock_fraud_approve):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 500, "spoof_location": "New York"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "accepted"

    a = client.get("/accounts/A").json()
    b = client.get("/accounts/B").json()
    assert a["balance"] == 4500.0
    assert b["balance"] == 3500.0
    # Sender's last-known location moves to wherever the (mocked) geolocation resolved.
    assert a["last_location"]["city"] == "Paris"


def test_approved_transfer_logs_accepted_incident(client, mock_geo_success, mock_fraud_approve):
    client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 100, "spoof_location": "New York"},
    )
    incidents = client.get("/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["verdict"] == "accepted"
    assert incidents[0]["from_account"] == "A"
    assert incidents[0]["amount"] == 100


def test_declined_transfer_leaves_balances_unchanged(client, mock_geo_success, mock_fraud_decline):
    res = client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 500, "spoof_location": "Sydney"},
    )
    assert res.status_code == 403
    assert "impossible travel detected" in res.json()["detail"]

    a = client.get("/accounts/A").json()
    b = client.get("/accounts/B").json()
    assert a["balance"] == 5000.0
    assert b["balance"] == 3000.0


def test_declined_transfer_logs_declined_incident_with_reason(client, mock_geo_success, mock_fraud_decline):
    client.post(
        "/transfer",
        json={"from_account": "A", "to_account": "B", "amount": 500, "spoof_location": "Sydney"},
    )
    incidents = client.get("/incidents").json()
    assert len(incidents) == 1
    assert incidents[0]["verdict"] == "declined-fraud"
    assert incidents[0]["reason"] == "impossible travel detected"


def test_incidents_are_returned_oldest_first(client, mock_geo_success, mock_fraud_approve):
    for amount in (10, 20, 30):
        client.post(
            "/transfer",
            json={"from_account": "A", "to_account": "B", "amount": amount, "spoof_location": "New York"},
        )
    incidents = client.get("/incidents").json()
    assert [i["amount"] for i in incidents] == [10, 20, 30]
