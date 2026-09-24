"""
Pactiva Kurumsal Webhook ve Olay Dağıtım Testleri (tests/test_webhooks.py)
"""

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from pactiva_core.api import app
from pactiva_core.database import init_db
from pactiva_core.webhooks import (
    compute_webhook_signature,
    verify_webhook_signature,
    create_webhook_subscription,
    list_webhook_subscriptions,
    is_event_matched,
    dispatch_event_to_webhooks,
)

client = TestClient(app)


@pytest.fixture
def temp_webhook_db(tmp_path):
    db_file = str(tmp_path / "test_webhooks.db")
    init_db(db_file)
    return db_file


def test_webhook_hmac_signature_verification():
    payload = '{"event": "escrow.locked", "amount": "5000.00"}'
    secret = "production_super_secret_webhook_key_32bytes"

    sig = compute_webhook_signature(payload, secret)
    assert len(sig) == 64
    assert verify_webhook_signature(payload, sig, secret) is True
    # Yanlış imza veya tahrif edilmiş payload
    assert verify_webhook_signature('{"tampered": true}', sig, secret) is False
    assert verify_webhook_signature(payload, "invalid_sig_000000000000000000000000000000000000000000000000000000000000", secret) is False


def test_event_matching_wildcards():
    assert is_event_matched("shift.checked_in", ["*"]) is True
    assert is_event_matched("shift.checked_in", ["shift.*"]) is True
    assert is_event_matched("escrow.disbursed", ["shift.*"]) is False
    assert is_event_matched("escrow.disbursed", ["escrow.disbursed", "escrow.locked"]) is True


def test_webhook_subscription_and_dispatch_lifecycle(temp_webhook_db):
    sub1 = create_webhook_subscription(
        target_url="https://erp.enterprise-corp.com/pactiva-hook",
        secret_key="secret_key_erp_1234567890123456",
        events=["escrow.*", "shift.completed"],
        db_path=temp_webhook_db,
    )
    assert sub1["id"] is not None
    assert sub1["is_active"] is True

    subs = list_webhook_subscriptions(active_only=True, db_path=temp_webhook_db)
    assert len(subs) == 1

    # Olay sevk et
    res = dispatch_event_to_webhooks(
        event_type="escrow.locked",
        payload={"job_id": "job_123", "locked_amount": "5400.00"},
        db_path=temp_webhook_db,
    )
    assert res["dispatched_count"] == 1
    delivery = res["deliveries"][0]
    assert delivery["subscription_id"] == sub1["id"]
    assert delivery["delivery_status"] == "delivered"
    assert len(delivery["signature"]) == 64


def test_webhook_api_endpoints():
    # 1. POST /api/v1/webhooks/subscribe
    sub_payload = {
        "target_url": "https://payroll.partner.org/webhook",
        "secret_key": "api_test_secret_key_32bytes_long_ok",
        "events": ["shift.*", "dispute.resolved"],
    }
    res_sub = client.post("/api/v1/webhooks/subscribe", json=sub_payload)
    assert res_sub.status_code == 201
    sub_data = res_sub.json()
    assert sub_data["id"] is not None
    assert sub_data["target_url"] == sub_payload["target_url"]

    # 2. GET /api/v1/webhooks/subscriptions
    res_list = client.get("/api/v1/webhooks/subscriptions")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) >= 1

    # 3. POST /api/v1/webhooks/dispatch
    disp_payload = {
        "event_type": "shift.checked_in",
        "payload": {"worker_id": str(uuid4()), "ptp_status": "synced"},
    }
    res_disp = client.post("/api/v1/webhooks/dispatch", json=disp_payload)
    assert res_disp.status_code == 200
    disp_data = res_disp.json()
    assert disp_data["event"] == "shift.checked_in"
    assert disp_data["dispatched_count"] >= 1
