"""
Pactiva — Prometheus & OpenMetrics Canlı Telemetri Motoru (pactiva_core/metrics.py)
Kubernetes, Grafana ve kurumsal SIEM sistemleri için anlık metrik çıktısı sağlar.
"""

from typing import Optional
from pactiva_core.database import get_db


def generate_prometheus_metrics(db_path: Optional[str] = None) -> str:
    """Sistemdeki canlı veritabanı durumunu OpenMetrics formatında metin olarak üretir."""
    lines = [
        "# HELP pactiva_up Sistem calisma ve saglik durumu (1 = aktif)",
        "# TYPE pactiva_up gauge",
        "pactiva_up 1",
    ]

    with get_db(db_path) as conn:
        # 1. Kilitli ve Ödenen Emanet Tutarları
        escrow_row = conn.execute(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN status = 'locked' THEN locked_amount ELSE 0 END), 0.0) as total_locked,
                COALESCE(SUM(CASE WHEN status = 'disbursed' THEN locked_amount ELSE 0 END), 0.0) as total_disbursed,
                COALESCE(SUM(withholding_tax_reserved), 0.0) as total_tax
            FROM escrow_accounts
            """
        ).fetchone()

        total_locked = escrow_row["total_locked"] if escrow_row else 0.0
        total_disbursed = escrow_row["total_disbursed"] if escrow_row else 0.0
        total_tax = escrow_row["total_tax"] if escrow_row else 0.0

        lines.extend([
            "# HELP pactiva_escrow_locked_try_total Emanet kasasinda bloke edilen toplam bütçe",
            "# TYPE pactiva_escrow_locked_try_total gauge",
            f"pactiva_escrow_locked_try_total {total_locked:.2f}",
            "# HELP pactiva_escrow_disbursed_try_total Emanet kasasindan calisanlara odenen toplam hak edis",
            "# TYPE pactiva_escrow_disbursed_try_total counter",
            f"pactiva_escrow_disbursed_try_total {total_disbursed:.2f}",
            "# HELP pactiva_tax_withheld_try_total 193 SK GVK 94 kapsaminda kesilen stopaj tutari",
            "# TYPE pactiva_tax_withheld_try_total counter",
            f"pactiva_tax_withheld_try_total {total_tax:.2f}",
        ])

        # 2. Denetim Blok Yüksekliği (Block Height)
        audit_row = conn.execute("SELECT COUNT(*) as cnt FROM audit_blocks").fetchone()
        audit_height = audit_row["cnt"] if audit_row else 0
        lines.extend([
            "# HELP pactiva_audit_block_height Kriptografik denetim zincirindeki muhurlu blok yuksekligi",
            "# TYPE pactiva_audit_block_height counter",
            f"pactiva_audit_block_height {audit_height}",
        ])

        # 3. İlan Durumları
        job_rows = conn.execute("SELECT status, count(*) as count FROM jobs GROUP BY status").fetchall()
        lines.append("# HELP pactiva_jobs_total Kategorize edilmis ilan sayilari")
        lines.append("# TYPE pactiva_jobs_total gauge")
        for r in job_rows:
            lines.append(f'pactiva_jobs_total{{status="{r["status"]}"}} {r["count"]}')

        # 4. Vardiya Durumları
        shift_rows = conn.execute("SELECT status, count(*) as count FROM shifts GROUP BY status").fetchall()
        lines.append("# HELP pactiva_shifts_total Kategorize edilmis mesai/vardiya sayilari")
        lines.append("# TYPE pactiva_shifts_total gauge")
        for r in shift_rows:
            lines.append(f'pactiva_shifts_total{{status="{r["status"]}"}} {r["count"]}')

    return "\n".join(lines) + "\n"
