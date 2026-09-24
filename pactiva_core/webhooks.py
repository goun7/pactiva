"""
Pactiva — Kurumsal Webhook ve Asenkron Olay Dağıtım Motoru (pactiva_core/webhooks.py)
ERP, muhasebe ve bordro sistemlerine anlık HMAC-SHA256 imzalı olay akışı sağlar.
"""

import fnmatch
import hmac
import hashlib
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pactiva_core.database import get_db


def compute_webhook_signature(payload_json: str, secret_key: str) -> str:
    """Olay yükünün HMAC-SHA256 özetini üretir (X-Pactiva-Signature)."""
    mac = hmac.new(secret_key.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()


def verify_webhook_signature(payload_json: str, signature: str, secret_key: str) -> bool:
    """Webhook alıcısının imza doğrulamasını güvenli zaman kıyasıyla yapar."""
    expected = compute_webhook_signature(payload_json, secret_key)
    return hmac.compare_digest(expected, signature)


def create_webhook_subscription(
    target_url: str,
    secret_key: str,
    events: List[str],
    subscription_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Sistemde yeni bir kurumsal webhook abonesi tanımlar."""
    sid = subscription_id or str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    events_json = json.dumps(events)

    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO webhook_subscriptions (id, target_url, secret_key, events, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (sid, target_url, secret_key, events_json, now),
        )

    return {
        "id": sid,
        "target_url": target_url,
        "secret_key": secret_key,
        "events": events,
        "is_active": True,
        "created_at": now,
    }


def list_webhook_subscriptions(
    active_only: bool = True,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Kayıtlı webhook abonelerini listeler."""
    with get_db(db_path) as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM webhook_subscriptions WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM webhook_subscriptions ORDER BY created_at DESC"
            ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        d["events"] = json.loads(d["events"])
        d["is_active"] = bool(d["is_active"])
        results.append(d)
    return results


def is_event_matched(event_type: str, patterns: List[str]) -> bool:
    """Olay tipinin abonenin dinlediği wildcard desenlerle eşleşip eşleşmediğini denetler."""
    for pattern in patterns:
        if pattern == "*" or fnmatch.fnmatch(event_type, pattern):
            return True
    return False


def dispatch_event_to_webhooks(
    event_type: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
    perform_network_call: bool = False,
) -> Dict[str, Any]:
    """
    Kritik bir olay gerçekleştiğinde (emanet kilidi, mesai tamamlama, tahkim kararı)
    ilgili abonelere imzalı webhook paketini sevk eder ve teslimat kütüğünü kaydeder.
    """
    now = datetime.now(timezone.utc).isoformat()
    payload_wrapper = {
        "event": event_type,
        "timestamp": now,
        "data": payload,
    }
    payload_json = json.dumps(payload_wrapper, sort_keys=True, default=str)

    subs = list_webhook_subscriptions(active_only=True, db_path=db_path)
    matched_subs = [s for s in subs if is_event_matched(event_type, s["events"])]

    deliveries = []
    for sub in matched_subs:
        delivery_id = str(uuid4())
        signature = compute_webhook_signature(payload_json, sub["secret_key"])
        status_code = None
        delivery_status = "delivered"

        if perform_network_call and sub["target_url"].startswith("http"):
            try:
                req = urllib.request.Request(
                    sub["target_url"],
                    data=payload_json.encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "X-Pactiva-Signature": signature,
                        "X-Pactiva-Event": event_type,
                        "User-Agent": "Pactiva-Webhook-Dispatcher/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    status_code = resp.status
                    delivery_status = "delivered" if 200 <= status_code < 300 else "failed"
            except Exception:
                status_code = 500
                delivery_status = "failed"
        else:
            # Yerel / test teslimatı
            status_code = 200
            delivery_status = "delivered"

        with get_db(db_path) as conn:
            conn.execute(
                """
                INSERT INTO webhook_deliveries (id, subscription_id, event_type, payload_json, signature_header, status_code, delivery_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (delivery_id, sub["id"], event_type, payload_json, signature, status_code, delivery_status, now),
            )

        deliveries.append({
            "delivery_id": delivery_id,
            "subscription_id": sub["id"],
            "target_url": sub["target_url"],
            "signature": signature,
            "status_code": status_code,
            "delivery_status": delivery_status,
        })

    return {
        "event": event_type,
        "dispatched_count": len(deliveries),
        "deliveries": deliveries,
    }
