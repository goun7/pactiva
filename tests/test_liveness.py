"""
Pactiva Biyometrik Canlılık ve Anti-Bot Testleri (tests/test_liveness.py)
"""

import pytest
from pactiva_core.liveness import verify_touch_liveness, calculate_shannon_entropy


def test_human_natural_jitter_passes():
    # Doğal insan dokunuş aralıkları (fizyolojik titreşim içerir)
    intervals = [225.0, 248.0, 210.0, 265.0, 230.0]
    res = verify_touch_liveness(intervals)
    assert res["is_human"] is True
    assert res["jitter_std_dev_ms"] > 3.0
    assert res["liveness_hash"] is not None


def test_superhuman_reaction_bot_rejected():
    # 50ms imkansız refleks (bot/makro)
    intervals = [50.0, 60.0, 55.0, 48.0]
    res = verify_touch_liveness(intervals)
    assert res["is_human"] is False
    assert res["error_code"] == "SUPERHUMAN_REFLEX_BOT"


def test_synthetic_macro_zero_jitter_rejected():
    # Robotik sabit zamanlama (std dev < 3ms)
    intervals = [200.0, 200.1, 200.0, 199.9, 200.0]
    res = verify_touch_liveness(intervals)
    assert res["is_human"] is False
    assert res["error_code"] == "SYNTHETIC_MACRO_DETECTED"


def test_shannon_entropy_calculation():
    # Tekdüze değerler -> sıfır entropi
    assert calculate_shannon_entropy([100.0, 100.0, 100.0]) == 0.0
    # Dağınık değerler -> pozitif entropi
    entropy = calculate_shannon_entropy([120.0, 180.0, 220.0, 290.0, 350.0])
    assert entropy > 1.0
