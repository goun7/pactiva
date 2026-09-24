"""
Pactiva IEEE 1588 PTP Donanım Saati Testleri (tests/test_ptp_clock.py)
"""

import time
import pytest
from pactiva_core.ptp_clock import (
    synchronize_and_verify_ptp,
    get_master_ptp_timestamp_ns,
    MAX_ALLOWED_CLOCK_SKEW_NS,
)


def test_ptp_synchronization_within_normal_bounds():
    master_now = get_master_ptp_timestamp_ns()
    # 50ms gecikmeli normal istemci zamanı
    client_ns = master_now - 50_000_000

    res = synchronize_and_verify_ptp(
        client_ptp_timestamp_ns=client_ns,
        estimated_network_rtt_ns=40_000_000,
    )
    assert res["is_synchronized"] is True
    assert abs(res["clock_offset_ms"]) < 200.0


def test_ptp_monotonic_clock_reversal_rejected():
    master_now = get_master_ptp_timestamp_ns()
    previous_event_ns = master_now - 100_000_000
    # Cihaz saati geriye alınmış
    client_ns = master_now - 200_000_000

    res = synchronize_and_verify_ptp(
        client_ptp_timestamp_ns=client_ns,
        previous_event_ptp_ns=previous_event_ns,
    )
    assert res["is_synchronized"] is False
    assert res["error_code"] == "MONOTONIC_CLOCK_REVERSAL"


def test_ptp_excessive_clock_skew_rejected():
    master_now = get_master_ptp_timestamp_ns()
    # 10 saniye ileri alınmış cihaz saati (> 2 saniye limit)
    client_ns = master_now + 10_000_000_000

    res = synchronize_and_verify_ptp(
        client_ptp_timestamp_ns=client_ns,
        max_skew_ns=MAX_ALLOWED_CLOCK_SKEW_NS,
    )
    assert res["is_synchronized"] is False
    assert res["error_code"] == "EXCESSIVE_CLOCK_SKEW"
