"""
Pactiva Vektör Eşleştirme Motoru Testleri (tests/test_vector_engine.py)
"""

import pytest
from pactiva_core.vector_engine import (
    cosine_similarity,
    generate_skill_vector_stub,
    rank_candidates_by_skill_match,
)


def test_cosine_similarity_edge_cases():
    # Özdeş vektörler -> 1.0
    v1 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v1), 0.001) == 1.0

    # Dik vektörler -> 0.0
    v2 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 0.0

    # Zıt vektörler -> -1.0
    v3 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), 0.001) == -1.0


def test_cosine_similarity_dimension_mismatch():
    with pytest.raises(ValueError, match="Vektör boyutları uyuşmuyor"):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])


def test_skill_vector_generation():
    vec1 = generate_skill_vector_stub(["kamera", "ışık"], dimension=32)
    vec2 = generate_skill_vector_stub(["kamera", "ışık"], dimension=32)
    assert len(vec1) == 32
    # Deterministik eşitlik
    assert vec1 == vec2


def test_rank_candidates_by_skill_match():
    job_vec = generate_skill_vector_stub(["kamera", "ışık", "dizi_seti"], dimension=64)

    candidates = [
        {
            "id": "cand_1",
            "name": "Tam Eşleşen Şef",
            "skills": ["kamera", "ışık", "dizi_seti"],
            "reputation_score": 95.0,
        },
        {
            "id": "cand_2",
            "name": "İnşaat Ustası",
            "skills": ["demir", "beton", "kalıp"],
            "reputation_score": 90.0,
        },
    ]

    ranked = rank_candidates_by_skill_match(job_vec, candidates, min_match_threshold=0.20)
    assert len(ranked) >= 1
    assert ranked[0]["name"] == "Tam Eşleşen Şef"
    assert ranked[0]["match_percentage"] > 90.0
