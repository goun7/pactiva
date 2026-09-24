"""
Pactiva — Dağıtık İstihdam, Bilişsel Yetkinlik ve Emanet Hak Ediş Altyapısı
Kapsamlı Birim Test Paketi (tests/test_pactiva_core.py)
"""

import pytest
from decimal import Decimal
from pactiva_core.math_models import (
    calculate_escrow_budget_lock,
    verify_wifi_rtt_distance,
    normalize_gamer_bias_reaction_time,
    calculate_quadratic_jury_slashing,
    compute_gib_net_gross_tax,
    calculate_ptp_overtime_payout,
)


class TestEscrowBudgetLock:
    """Proof-of-Budget Escrow Kilit Hesaplaması Testleri"""

    def test_standard_escrow_calculation(self):
        # Saatlik 500 TL, 10 saat, %20 fazla mesai tamponu: 500 * 10 * 1.20 = 6000.00 TL
        rate = Decimal("500.00")
        hours = Decimal("10.0")
        margin = Decimal("0.20")
        result = calculate_escrow_budget_lock(rate, hours, margin)
        assert result == Decimal("6000.00")

    def test_custom_margin(self):
        rate = Decimal("450.00")
        hours = Decimal("8.0")
        margin = Decimal("0.15")  # %15 marj: 3600 * 1.15 = 4140.00
        result = calculate_escrow_budget_lock(rate, hours, margin)
        assert result == Decimal("4140.00")

    def test_invalid_negative_rate_raises(self):
        with pytest.raises(ValueError, match="Taban saatlik ücret sıfırdan büyük olmalıdır"):
            calculate_escrow_budget_lock(Decimal("-100"), Decimal("8"))

    def test_invalid_zero_hours_raises(self):
        with pytest.raises(ValueError, match="Öngörülen çalışma süresi sıfırdan büyük olmalıdır"):
            calculate_escrow_budget_lock(Decimal("500"), Decimal("0"))


class TestWiFiRTTDistance:
    """IEEE 802.11mc Wi-Fi RTT Uçuş Süresi Doğrulama Testleri"""

    def test_standard_rtt_distance(self):
        # 100 nanosaniyelik gidiş-dönüş uçuş süresi: (0.299792458 * 100) / 2 = ~14.99 metre
        t1 = 1000
        t2 = 1050
        t3 = 1100
        t4 = 1250
        # (1250 - 1000) - (1100 - 1050) = 250 - 50 = 200 ns -> d = 29.98 m
        dist = verify_wifi_rtt_distance(t1, t2, t3, t4)
        assert dist == pytest.approx(29.98, rel=1e-2)

    def test_close_proximity_rtt(self):
        # 10 ns uçuş süresi: (0.299792458 * 10) / 2 = ~1.50 metre
        t1 = 0
        t2 = 5
        t3 = 10
        t4 = 25  # (25 - 0) - (10 - 5) = 25 - 5 = 20 ns -> 2.998 m
        dist = verify_wifi_rtt_distance(t1, t2, t3, t4)
        assert dist == pytest.approx(3.00, rel=1e-2)

    def test_chronological_violation_raises(self):
        with pytest.raises(ValueError, match="kronolojik sıraya aykırı"):
            verify_wifi_rtt_distance(t1=100, t2=50, t3=40, t4=90)


class TestGamerBiasNormalizer:
    """Log-Normal Yaş ve Oyuncu Refleks Dengeleme Testleri"""

    def test_young_gamer_vs_older_non_gamer(self):
        # 20 yaşında oyuncu 180 ms reaksiyon
        z_gamer = normalize_gamer_bias_reaction_time(180.0, age=20, is_gamer=True)
        # 45 yaşında oyuncu olmayan 260 ms reaksiyon
        z_mature = normalize_gamer_bias_reaction_time(260.0, age=45, is_gamer=False)
        # Normalizasyon sonrası ikisinin z-skorları birbirine yakınlaşmalıdır
        assert abs(z_gamer - z_mature) < 1.0

    def test_invalid_age_raises(self):
        with pytest.raises(ValueError, match="Yaş 18 ile 100 arasında olmalıdır"):
            normalize_gamer_bias_reaction_time(200.0, age=15, is_gamer=False)


class TestQuadraticJurySlashing:
    """7 Üyeli Jüri Karesel Schelling Konsensüsü ve Slashing Testleri"""

    def test_unanimous_jury_no_slashing(self):
        # 7 jüri de işçi lehine oy kullanıyor (+1.0)
        votes = [Decimal("1.0")] * 7
        stakes = [Decimal("1000.00")] * 7
        consensus, slashed, rewards = calculate_quadratic_jury_slashing(votes, stakes)
        assert consensus == Decimal("1.00")
        assert all(s == Decimal("0.00") for s in slashed)
        assert all(r == Decimal("0.00") for r in rewards)

    def test_malicious_outlier_juror_is_slashed(self):
        # 6 jüri +1.0 oy verirken 1 kötü niyetli jüri -1.0 veriyor
        votes = [Decimal("1.0")] * 6 + [Decimal("-1.0")]
        stakes = [Decimal("1000.00")] * 7
        consensus, slashed, rewards = calculate_quadratic_jury_slashing(votes, stakes)

        # Konsensüs güçlü pozitif olmalı
        assert consensus > Decimal("0.70")
        # 7. jürinin teminatı (%30 = 300 TL) kesilmeli
        assert slashed[-1] == Decimal("300.00")
        assert all(s == Decimal("0.00") for s in slashed[:6])
        # Kesilen 300 TL, dürüst 6 jüriye paylaştırılmalı (50 TL her birine)
        assert all(r == Decimal("50.00") for r in rewards[:6])
        assert rewards[-1] == Decimal("0.00")


class TestGIBTaxWithholding:
    """GİB Elektronik Gider Pusulası Net-Brüt Tevkifat Testleri"""

    def test_standard_ten_percent_withholding(self):
        # 4.500 TL net hak ediş: Brüt = 4500 / 0.90 = 5000 TL, Stopaj = 500 TL
        net = Decimal("4500.00")
        tax = compute_gib_net_gross_tax(net, withholding_tax_rate=Decimal("0.10"))
        assert tax["net_payout"] == Decimal("4500.00")
        assert tax["gross_amount"] == Decimal("5000.00")
        assert tax["withholding_tax_deducted"] == Decimal("500.00")
        assert tax["tax_rate_applied"] == Decimal("0.10")

    def test_custom_tax_rate(self):
        # 8.000 TL net, %20 stopaj: Brüt = 8000 / 0.80 = 10000 TL, Stopaj = 2000 TL
        net = Decimal("8000.00")
        tax = compute_gib_net_gross_tax(net, withholding_tax_rate=Decimal("0.20"))
        assert tax["gross_amount"] == Decimal("10000.00")
        assert tax["withholding_tax_deducted"] == Decimal("2000.00")


class TestPTPOvertimePayout:
    """4857 Sayılı İş Kanunu Fazla Mesai ve Gece Mesaisi Testleri"""

    def test_overtime_and_night_shift_breakdown(self):
        # Saatlik ücret: 300 TL (Dakikada 5 TL)
        # 480 dk normal mesai: 480 * 5 = 2400 TL
        # 120 dk fazla mesai (%50 zam = 7.5 TL/dk): 120 * 7.5 = 900 TL
        # 60 dk gece mesaisi (%30 zam = 1.5 TL/dk ek prim): 60 * 1.5 = 90 TL
        # Toplam: 2400 + 900 + 90 = 3390 TL
        hourly = Decimal("300.00")
        res = calculate_ptp_overtime_payout(
            regular_minutes=480,
            overtime_minutes=120,
            night_shift_minutes=60,
            hourly_rate=hourly,
        )
        assert res["regular_pay"] == Decimal("2400.00")
        assert res["overtime_pay"] == Decimal("900.00")
        assert res["night_differential_pay"] == Decimal("90.00")
        assert res["total_gross_payout"] == Decimal("3390.00")
