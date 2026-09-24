"""
Pactiva — Acil Yedekleme ve No-Show Dağıtım SLA Motoru (pactiva_core/dispatch.py)
Şantiye veya film setinde vardiyaya gelmeyen işçi durumunda 10 dakikalık hızlı yedekleme boru hattı.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from pactiva_core.math_models import TWO_PLACES, normalize_gamer_bias_reaction_time


RUSH_BONUS_MULTIPLIER = Decimal("1.20")  # %20 Acil çağrı primi
MAX_DISPATCH_RADIUS_KM = 15.0
MIN_REPUTATION_THRESHOLD = 75.0


def rank_emergency_standby_candidates(
    candidates: List[Dict[str, Any]],
    max_radius_km: float = MAX_DISPATCH_RADIUS_KM,
    min_reputation: float = MIN_REPUTATION_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Acil durum çağrısı için coğrafi yakınlık, bilişsel tepki hızı ve itibar puanına göre
    en uygun yedek adayları derecelendirir.
    """
    ranked: List[Dict[str, Any]] = []

    for cand in candidates:
        dist = float(cand.get("distance_km", 999.0))
        rep = float(cand.get("reputation_score", 0.0))
        is_avail = bool(cand.get("is_available", True))

        if not is_avail or dist > max_radius_km or rep < min_reputation:
            continue

        # 1. Coğrafi yakınlık skoru (0.0 - 1.0)
        proximity_score = max(0.0, 1.0 - (dist / max_radius_km))

        # 2. İtibar puanı skoru (0.0 - 1.0)
        reputation_score_norm = min(1.0, max(0.0, rep / 100.0))

        # 3. Bilişsel tepki hızı skoru (GamerBiasNormalizer z-skoru üzerinden)
        reaction_ms = float(cand.get("reaction_time_ms", 250.0))
        age = int(cand.get("age", 25))
        weekly_gaming_hours = float(cand.get("weekly_gaming_hours", 0.0))
        is_gamer = weekly_gaming_hours >= 5.0 or bool(cand.get("is_gamer", False))
        z_score = normalize_gamer_bias_reaction_time(
            rt_raw_ms=reaction_ms,
            age=age,
            is_gamer=is_gamer,
        )

        # z-skoru ne kadar negatifse tepki hızı o kadar yüksektir (-2.0 -> süper hızlı, +2.0 -> yavaş)
        # 0.0 - 1.0 aralığına normalize edilir
        cognitive_score = max(0.0, min(1.0, (2.0 - z_score) / 4.0))

        # Ağırlıklı Bileşik Skor: %45 Mesafe, %35 Bilişsel Hız, %20 İtibar
        composite_score = (
            (0.45 * proximity_score) +
            (0.35 * cognitive_score) +
            (0.20 * reputation_score_norm)
        )

        ranked.append({
            "candidate_id": cand.get("id"),
            "name": cand.get("name", "Gizli Aday"),
            "distance_km": dist,
            "eta_minutes": max(3, int(dist * 2.2)),
            "reputation_score": rep,
            "cognitive_z_score": z_score,
            "composite_score": round(composite_score, 4),
            "phone_encrypted": cand.get("phone_number_encrypted", ""),
        })

    # En yüksek bileşik skora göre sıralama
    ranked.sort(key=lambda x: x["composite_score"], reverse=True)
    return ranked


def trigger_emergency_dispatch(
    job_id: str,
    shift_id: str,
    base_hourly_rate: Decimal,
    available_candidates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    No-show durumunda acil yedek işçi tahsis döngüsünü tetikler.
    +20% acil çağrı primi hesaplanır ve yedek adaya acil bildirim paketi hazırlanır.
    """
    candidates = list(available_candidates) if available_candidates is not None else []
    if not candidates:
        try:
            from pactiva_core.repository import PactivaRepository
            db_workers = PactivaRepository().list_workers(min_reputation=75.0)
            candidates = [
                {
                    "id": str(w["id"]),
                    "name": f"Sertifikalı Yedek #{str(w['id'])[:8]}",
                    "distance_km": 4.5,
                    "reputation_score": float(w.get("reputation_score", 90.0)),
                    "reaction_time_ms": 220.0,
                    "age": 27,
                    "is_available": True,
                }
                for w in db_workers
            ]
        except Exception:
            candidates = []

    ranked_pool = rank_emergency_standby_candidates(candidates)
    if not ranked_pool:
        return {
            "success": False,
            "job_id": job_id,
            "shift_id": shift_id,
            "status": "EXHAUSTED",
            "message": "15 km yarıçapında uygun itibar puanına sahip acil yedek aday bulunamadı.",
            "candidates_evaluated": len(available_candidates),
        }

    primary_candidate = ranked_pool[0]
    rush_hourly_rate = (base_hourly_rate * RUSH_BONUS_MULTIPLIER).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    rush_premium_hourly = (rush_hourly_rate - base_hourly_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return {
        "success": True,
        "job_id": job_id,
        "shift_id": shift_id,
        "status": "DISPATCH_OFFERED",
        "primary_assigned_candidate": primary_candidate,
        "standby_pool_size": len(ranked_pool),
        "base_hourly_rate": base_hourly_rate,
        "rush_hourly_rate": rush_hourly_rate,
        "rush_premium_hourly": rush_premium_hourly,
        "sla_target_minutes": 10,
        "estimated_arrival_minutes": primary_candidate["eta_minutes"],
    }
