"""
Pactiva — Vektör Benzerlik ve Semantik Yetkinlik Eşleştirme Motoru (pactiva_core/vector_engine.py)
pgvector HNSW uyumlu kosinüs benzerliği ve aday yetkinlik eşleştirme katmanı.
"""

import hashlib
import math
from typing import Any, Dict, List, Optional


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    İki yetkinlik vektörü arasındaki kosinüs benzerliğini hesaplar (-1.0 ile +1.0 arası).
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vektör boyutları uyuşmuyor: {len(vec_a)} != {len(vec_b)}")
    if not vec_a:
        raise ValueError("Vektör boş olamaz.")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    # Sayısal taşmaları sınırla
    return max(-1.0, min(1.0, similarity))


def generate_skill_vector_stub(skills: List[str], dimension: int = 64) -> List[float]:
    """
    Dış bağımlılık gerektirmeksizin deterministik, normalize edilmiş yetkinlik vektörü üretir.
    """
    raw_vec = [0.0] * dimension
    for skill in skills:
        cleaned = skill.strip().lower()
        if not cleaned:
            continue
        h = hashlib.sha256(cleaned.encode("utf-8")).digest()
        for i in range(dimension):
            byte_val = h[i % len(h)]
            raw_vec[i] += (byte_val / 128.0) - 1.0

    norm = math.sqrt(sum(x * x for x in raw_vec))
    if norm == 0.0:
        return [0.0] * dimension
    return [round(x / norm, 6) for x in raw_vec]


def rank_candidates_by_skill_match(
    job_skills_vector: List[float],
    candidates: List[Dict[str, Any]],
    min_match_threshold: float = 0.50,
) -> List[Dict[str, Any]]:
    """
    İş ilanı vektörüne göre adayları kosinüs benzerliği üzerinden sıralar.
    """
    scored = []
    for cand in candidates:
        cand_vec = cand.get("skills_vector")
        if not cand_vec:
            # skills listesi verilmişse vektör üret
            skills_list = cand.get("skills", [])
            cand_vec = generate_skill_vector_stub(skills_list, dimension=len(job_skills_vector))

        sim = cosine_similarity(job_skills_vector, cand_vec)
        if sim >= min_match_threshold:
            scored.append({
                "candidate_id": cand.get("id"),
                "name": cand.get("name", "Aday"),
                "similarity_score": round(sim, 4),
                "match_percentage": round(max(0.0, sim) * 100, 1),
                "reputation_score": cand.get("reputation_score", 100.0),
                "skills": cand.get("skills", []),
            })

    # Benzerlik skoruna göre azalan sırada diz
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored
