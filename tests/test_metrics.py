"""
Pactiva Prometheus & OpenMetrics Telemetri Testleri (tests/test_metrics.py)
"""

from fastapi.testclient import TestClient
from pactiva_core.api import app
from pactiva_core.metrics import generate_prometheus_metrics

client = TestClient(app)


def test_prometheus_metrics_generation():
    metrics_text = generate_prometheus_metrics()
    assert "pactiva_up 1" in metrics_text
    assert "pactiva_escrow_locked_try_total" in metrics_text
    assert "pactiva_audit_block_height" in metrics_text


def test_metrics_api_endpoint():
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "pactiva_up 1" in res.text
