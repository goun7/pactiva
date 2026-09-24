"""
Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik ve Emanet Hak Ediş Altyapısı
Çekirdek Matematiksel ve Hukuki Hesaplama Modülü (pactiva_core/math_models.py)
Tüm finansal hesaplamalarda 4857 SK, 4904 SK ve GVK 94 uyumlu Decimal sınıfı kullanılır.
"""

import math
from decimal import Decimal, ROUND_HALF_UP

# Işık hızı (metre / nanosaniye): 0.299792458 m/ns
SPEED_OF_LIGHT_M_PER_NS = 0.299792458

# Finansal yuvarlama sabiti (2 basamak, kuruş hassasiyeti)
TWO_PLACES = Decimal("0.01")


def calculate_escrow_budget_lock(
    base_hourly_rate: Decimal,
    expected_hours: Decimal,
    overtime_margin: Decimal = Decimal("0.20"),
) -> Decimal:
    """
    İşverenin ilan açarken emanet kasasında kilitlemesi gereken asgari bütçeyi hesaplar.
    Formül: Lock(B) >= W_base * H_expected * (1 + mu_overtime)
    """
    if base_hourly_rate <= Decimal("0"):
        raise ValueError("Taban saatlik ücret sıfırdan büyük olmalıdır.")
    if expected_hours <= Decimal("0"):
        raise ValueError("Öngörülen çalışma süresi sıfırdan büyük olmalıdır.")
    if overtime_margin < Decimal("0"):
        raise ValueError("Fazla mesai marjı negatif olamaz.")

    total_multiplier = Decimal("1") + overtime_margin
    raw_amount = base_hourly_rate * expected_hours * total_multiplier
    return raw_amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def verify_wifi_rtt_distance(
    t1: int,
    t2: int,
    t3: int,
    t4: int,
) -> float:
    """
    IEEE 802.11mc Fine Timing Measurement (FTM) ile erişim noktası ve telefon arasındaki mesafeyi hesaplar.
    Formül: d = (c * [(t4 - t1) - (t3 - t2)]) / 2
    """
    if t4 < t1 or t3 < t2:
        raise ValueError("Zaman damgaları kronolojik sıraya aykırı: t4 >= t1 ve t3 >= t2 olmalıdır.")

    round_trip_time_ns = (t4 - t1) - (t3 - t2)
    if round_trip_time_ns < 0:
        raise ValueError("Uçuş süresi negatif olamaz (Donanımsal saat sapması veya spoofing şüphesi).")

    distance_meters = (SPEED_OF_LIGHT_M_PER_NS * round_trip_time_ns) / 2.0
    return round(distance_meters, 2)


def normalize_gamer_bias_reaction_time(
    rt_raw_ms: float,
    age: int,
    is_gamer: bool,
) -> float:
    """
    Video oyunu alışkanlığı ve yaşa bağlı fizyolojik refleks avantajını log-normal dağılımla normalize eder.
    Formül: Z_norm = (ln(RT_raw) - mu(Yaş, GamerStatus)) / sigma(Yaş, GamerStatus)
    Çıktı: Standartlaştırılmış Z-Skoru (0 ortalama, 1 varyans)
    """
    if rt_raw_ms <= 0:
        raise ValueError("Ham reaksiyon süresi sıfırdan büyük olmalıdır.")
    if age < 18 or age > 100:
        raise ValueError("Yaş 18 ile 100 arasında olmalıdır.")

    # Ampirik bilişsel psikoloji tablosu (2026 normları):
    # Genç ve oyuncu bireylerin reaksiyon süreleri belirgin şekilde daha kısadır.
    base_mu = 5.40 + (age - 20) * 0.005  # Yaşlandıkça tepki süresi log-ortalaması artar
    if is_gamer:
        base_mu -= 0.18  # Oyuncuların log-merkezi daha düşüktür (daha hızlıdır)

    sigma = 0.22  # Log-normal standart sapma

    log_rt = math.log(rt_raw_ms)
    z_norm = (log_rt - base_mu) / sigma
    return round(z_norm, 3)


def calculate_quadratic_jury_slashing(
    votes: list[Decimal],
    stakes: list[Decimal],
    consensus_threshold: Decimal = Decimal("0.50"),
    slash_rate: Decimal = Decimal("0.30"),
) -> tuple[Decimal, list[Decimal], list[Decimal]]:
    """
    7 Üyeli Jüri için karesel ağırlıklı Schelling konsensüsü ve teminat kesintisini (Slashing) hesaplar.
    Oylar: [-1.0 (İşveren lehine), +1.0 (İşçi lehine)]
    Karesel ağırlık: w_i = sqrt(stake_i)
    Çıktı: (Konsensüs Skoru, Ceza Miktarları Listesi, Hak Edilen Ödüller Listesi)
    """
    if len(votes) != len(stakes):
        raise ValueError("Oy ve teminat listeleri eşit uzunlukta olmalıdır.")
    if not votes:
        raise ValueError("Jüri listesi boş olamaz.")

    total_weight = Decimal("0")
    weighted_vote_sum = Decimal("0")

    # 1. Karesel Ağırlıklı Konsensüs Hesabı
    for v, s in zip(votes, stakes):
        if s <= Decimal("0"):
            raise ValueError("Jüri teminatı sıfırdan büyük olmalıdır.")
        if v < Decimal("-1.0") or v > Decimal("1.0"):
            raise ValueError("Oy kararı [-1.0, 1.0] aralığında olmalıdır.")

        # Karesel oy ağırlığı: sqrt(stake)
        weight = Decimal(str(math.sqrt(float(s))))
        weighted_vote_sum += v * weight
        total_weight += weight

    consensus_point = (weighted_vote_sum / total_weight).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # 2. Sapma Kontrolü ve Slashing
    slashed_amounts: list[Decimal] = []
    rewards: list[Decimal] = []
    total_slashed_pool = Decimal("0")

    for v, s in zip(votes, stakes):
        deviation = abs(v - consensus_point)
        # Eğer oy konsensüs ile zıt yöndeyse veya sapma eşikten büyükse cezalandır
        if deviation > consensus_threshold and (v * consensus_point < Decimal("0")):
            penalty = (s * slash_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            slashed_amounts.append(penalty)
            total_slashed_pool += penalty
        else:
            slashed_amounts.append(Decimal("0.00"))

    # 3. Konsensüse Uyan Jüriye Ödül Dağıtımı (Ceza havuzundan eşit pay)
    honest_jurors_count = sum(1 for p in slashed_amounts if p == Decimal("0.00"))
    for p in slashed_amounts:
        if p == Decimal("0.00") and honest_jurors_count > 0:
            reward = (total_slashed_pool / Decimal(str(honest_jurors_count))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            rewards.append(reward)
        else:
            rewards.append(Decimal("0.00"))

    return consensus_point, slashed_amounts, rewards


def compute_gib_net_gross_tax(
    net_payout: Decimal,
    withholding_tax_rate: Decimal = Decimal("0.10"),
) -> dict[str, Decimal]:
    """
    193 Sayılı Gelir Vergisi Kanunu Madde 94 uyarınca GİB Elektronik Gider Pusulası Net-Brüt dönüşümünü yapar.
    Formül: Brüt = Net / (1 - Stopaj Oranı)
            Stopaj Kesintisi = Brüt * Stopaj Oranı
    """
    if net_payout <= Decimal("0"):
        raise ValueError("Net hak ediş tutarı sıfırdan büyük olmalıdır.")
    if withholding_tax_rate < Decimal("0") or withholding_tax_rate >= Decimal("1"):
        raise ValueError("Stopaj oranı [0, 1) aralığında olmalıdır.")

    divisor = Decimal("1") - withholding_tax_rate
    gross_amount = (net_payout / divisor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    withholding_amount = (gross_amount - net_payout).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    return {
        "net_payout": net_payout,
        "gross_amount": gross_amount,
        "withholding_tax_deducted": withholding_amount,
        "tax_rate_applied": withholding_tax_rate,
    }


def calculate_ptp_overtime_payout(
    regular_minutes: int,
    overtime_minutes: int,
    night_shift_minutes: int,
    hourly_rate: Decimal,
) -> dict[str, Decimal]:
    """
    4857 Sayılı İş Kanunu Madde 41 (%50 fazla mesai) ve Madde 69 (%30 gece mesaisi) uyarınca hak ediş hesaplar.
    """
    if regular_minutes < 0 or overtime_minutes < 0 or night_shift_minutes < 0:
        raise ValueError("Mesai süreleri negatif olamaz.")
    if hourly_rate <= Decimal("0"):
        raise ValueError("Saatlik ücret sıfırdan büyük olmalıdır.")

    minute_rate = hourly_rate / Decimal("60")

    # 1. Normal Mesai
    regular_pay = (Decimal(str(regular_minutes)) * minute_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # 2. Fazla Mesai (%50 zamlı: 1.50 katsayı)
    overtime_rate = minute_rate * Decimal("1.50")
    overtime_pay = (Decimal(str(overtime_minutes)) * overtime_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # 3. Gece Mesaisi Primi (%30 ilave gece farkı: 0.30 katsayı)
    night_rate = minute_rate * Decimal("0.30")
    night_pay = (Decimal(str(night_shift_minutes)) * night_rate).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    total_gross = regular_pay + overtime_pay + night_pay

    return {
        "regular_pay": regular_pay,
        "overtime_pay": overtime_pay,
        "night_differential_pay": night_pay,
        "total_gross_payout": total_gross,
    }
