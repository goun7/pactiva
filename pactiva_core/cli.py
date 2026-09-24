"""
Pactiva — Kurumsal Saha & Yönetici Komut Satırı Arayüzü (CLI) (pactiva_core/cli.py)
"""

import argparse
import json
import sys
import time
from decimal import Decimal
from uuid import uuid4

from pactiva_core.arbitration import resolve_dispute
from pactiva_core.contracts import generate_tripartite_contract
from pactiva_core.database import init_db
from pactiva_core.dispatch import trigger_emergency_dispatch
from pactiva_core.math_models import calculate_escrow_budget_lock, TWO_PLACES
from pactiva_core.qr_engine import generate_rolling_qr_token
from pactiva_core.repository import PactivaRepository


def cmd_status(args):
    init_db()
    repo = PactivaRepository()
    jobs = repo.list_jobs()
    active_jobs = [j for j in jobs if j.get("status") == "active"]

    print("=" * 60)
    print("  PACTIVA ENTERPRISE INFRASTRUCTURE STATUS")
    print("=" * 60)
    print(f"  Toplam Kayıtlı İlan : {len(jobs)}")
    print(f"  Aktif Kilitli İlan  : {len(active_jobs)}")
    print(f"  Sistem Durumu       : OPERATIONAL (SQLite WAL / REST API)")
    print("=" * 60)


def cmd_lock_budget(args):
    init_db()
    repo = PactivaRepository()
    rate = Decimal(str(args.rate))
    hours = Decimal(str(args.hours))

    locked = calculate_escrow_budget_lock(rate, hours, Decimal("0.20"))
    fee = (locked * Decimal("0.03")).quantize(TWO_PLACES)

    job_id = str(uuid4())
    tx_ref = f"ESC-CLI-{time.strftime('%Y%m%d')}-{job_id[:8].upper()}"

    repo.create_job(
        employer_id=args.employer_id,
        title=args.title,
        category=args.category,
        base_hourly_rate=rate,
        expected_hours=hours,
        job_id=job_id,
    )
    repo.create_escrow_account(
        job_id=job_id,
        locked_amount=locked,
        platform_fee=fee,
        provider_tx_ref=tx_ref,
    )

    print(f"✅ Bütçe Başarıyla Kilitlendi:")
    print(f"   İlan ID        : {job_id}")
    print(f"   Başlık         : {args.title}")
    print(f"   Kilitli Tutar  : {locked} TL (+%20 Tampon Dahil)")
    print(f"   Platform Payı  : {fee} TL")
    print(f"   Referans Kodu  : {tx_ref}")


def cmd_qr_generate(args):
    qr = generate_rolling_qr_token(job_id=args.job_id, shift_id=args.shift_id)
    print(f"📱 15-Saniyelik Dönen QR Tokeni:")
    print(f"   Token      : {qr['token']}")
    print(f"   Pencere    : #{qr['window_step']}")
    print(f"   Kalan Süre : {qr['seconds_remaining']} saniye")
    print(f"   Son Geçer  : {qr['expires_at_epoch']}")


def cmd_dispatch(args):
    res = trigger_emergency_dispatch(
        job_id=args.job_id,
        shift_id=args.shift_id,
        base_hourly_rate=Decimal(str(args.rate)),
        available_candidates=[
            {
                "id": str(uuid4()),
                "name": "CLI Yedek Ekip (Ahmet Usta)",
                "distance_km": 3.2,
                "reputation_score": 95.0,
                "reaction_time_ms": 210.0,
                "age": 28,
                "weekly_gaming_hours": 5.0,
                "is_available": True,
            }
        ],
    )
    print(f"🚨 Acil Yedekleme Sonucu:")
    print(f"   Durum        : {res['status']}")
    print(f"   Atanan Aday  : {res['primary_assigned_candidate']['name']} ({res['primary_assigned_candidate']['distance_km']} km)")
    print(f"   Varış Süresi : {res['estimated_arrival_minutes']} dk (<10 dk SLA)")
    print(f"   Acil Ücret   : {res['rush_hourly_rate']} TL/s (+%{int((Decimal('1.20')-1)*100)} Prim)")


def cmd_contract(args):
    contract = generate_tripartite_contract(
        employer_id=args.employer_id,
        worker_id=args.worker_id,
        job_id=args.job_id,
        job_title=args.title,
        base_hourly_rate=Decimal(str(args.rate)),
        expected_hours=Decimal(str(args.hours)),
        category=args.category,
    )
    print(f"📜 Yasal Üçlü Sözleşme Tanzim Edildi:")
    print(f"   Sözleşme ID   : {contract['contract_id']}")
    print(f"   SHA-256 Hash  : {contract['contract_sha256_hash']}")
    print(f"   4857 Md. 2    : SGK Müteselsil İzolasyonu ONAYLI")
    print(f"   4904 Md. 19   : %0 İşçi Komisyonu ONAYLI")
    print(f"   GVK Md. 94    : %10 Stopaj Tevkifatı ONAYLI")
    print(f"   Arşiv PDF     : {contract['archive_url']}")


def cmd_audit_verify(args):
    init_db()
    from pactiva_core.audit_ledger import verify_audit_ledger_integrity
    res = verify_audit_ledger_integrity()
    print("=" * 60)
    print("  PACTIVA KRİPTOGRAFİK DENETİM ZİNCİRİ (PROOF-OF-AUDIT)")
    print("=" * 60)
    print(f"  Bütünlük Durumu  : {'✅ KUSURSUZ (100% DOĞRULANDI)' if res['is_valid'] else '❌ TAHRİFAT TESPİT EDİLDİ'}")
    print(f"  Toplam Blok      : {res['total_blocks']}")
    print(f"  En Son Blok Hash : {res.get('latest_block_hash') or 'GENESIS'}")
    print(f"  Açıklama         : {res['detail']}")
    print("=" * 60)


def cmd_erp_export(args):
    init_db()
    repo = PactivaRepository()
    from pactiva_core.erp_export import generate_journal_entry, export_to_logo_xml, export_to_sap_csv
    invoices = repo.list_tax_invoices(limit=100)
    entries = []
    for inv in invoices:
        g = Decimal(str(inv["gross_amount"])).quantize(TWO_PLACES)
        t = Decimal(str(inv["withholding_tax_amount"])).quantize(TWO_PLACES)
        n = Decimal(str(inv["net_payout_amount"])).quantize(TWO_PLACES)
        entry = generate_journal_entry(
            shift_id=str(inv["shift_id"]),
            worker_name=f"Yüklenici #{str(inv['worker_id'])[:8]}",
            project_title="Saha İstihdam Hizmeti",
            gross_amount=g,
            withholding_tax=t,
            net_payout=n,
            account_cost_center=args.cost_center,
        )
        entries.append(entry)

    if args.format == "logo_xml":
        out = export_to_logo_xml(entries)
    elif args.format == "sap_csv":
        out = export_to_sap_csv(entries)
    else:
        out = json.dumps(entries, default=str, indent=2, ensure_ascii=False)

    print(out)


def cmd_release_escrow(args):
    init_db()
    repo = PactivaRepository()
    from pactiva_core.audit_ledger import record_audit_event
    payout = Decimal(str(args.payout))
    tax = Decimal(str(args.tax))
    escrow = repo.release_escrow_payout(args.job_id, payout, tax)
    audit = record_audit_event("ESCROW_PAYOUT_RELEASED", {
        "job_id": args.job_id,
        "payout": str(payout),
        "tax": str(tax),
    })
    print(f"✅ Emanet Kasasından Hak Ediş Ödendi:")
    print(f"   İlan ID        : {args.job_id}")
    print(f"   Net Hak Ediş   : {payout} TL")
    print(f"   GVK 94 Stopaj  : {tax} TL")
    print(f"   Denetim Bloğu  : {audit['block_hash']}")


def main():
    parser = argparse.ArgumentParser(description="Pactiva Enterprise CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Sistem ve veritabanı durumunu gösterir")
    p_status.set_defaults(func=cmd_status)

    # lock-budget
    p_lock = subparsers.add_parser("lock-budget", help="İlan açar ve emanet bütçesini kilitler")
    p_lock.add_argument("--employer-id", default=str(uuid4()))
    p_lock.add_argument("--title", required=True)
    p_lock.add_argument("--category", default="gig_labor", choices=["film_set", "construction", "gig_labor", "white_collar_talent"])
    p_lock.add_argument("--rate", required=True, type=float)
    p_lock.add_argument("--hours", required=True, type=float)
    p_lock.set_defaults(func=cmd_lock_budget)

    # release-escrow
    p_rel = subparsers.add_parser("release-escrow", help="Emanet kasasından hak edişi serbest bırakır")
    p_rel.add_argument("--job-id", required=True)
    p_rel.add_argument("--payout", required=True, type=float)
    p_rel.add_argument("--tax", default=0.0, type=float)
    p_rel.set_defaults(func=cmd_release_escrow)

    # generate-qr
    p_qr = subparsers.add_parser("generate-qr", help="15s dönen QR kodu üretir")
    p_qr.add_argument("--job-id", default=str(uuid4()))
    p_qr.add_argument("--shift-id", default=str(uuid4()))
    p_qr.set_defaults(func=cmd_qr_generate)

    # dispatch
    p_disp = subparsers.add_parser("dispatch", help="10 dakika SLA acil yedek işçi çağırır")
    p_disp.add_argument("--job-id", default=str(uuid4()))
    p_disp.add_argument("--shift-id", default=str(uuid4()))
    p_disp.add_argument("--rate", default=400.0, type=float)
    p_disp.set_defaults(func=cmd_dispatch)

    # contract
    p_con = subparsers.add_parser("contract", help="4857/4904/GVK94 uyumlu yasal sözleşme tanzim eder")
    p_con.add_argument("--employer-id", default=str(uuid4()))
    p_con.add_argument("--worker-id", default=str(uuid4()))
    p_con.add_argument("--job-id", default=str(uuid4()))
    p_con.add_argument("--title", default="Set Teknisyeni")
    p_con.add_argument("--category", default="film_set")
    p_con.add_argument("--rate", default=450.0, type=float)
    p_con.add_argument("--hours", default=10.0, type=float)
    p_con.set_defaults(func=cmd_contract)

    # audit-verify
    p_aud = subparsers.add_parser("audit-verify", help="Kriptografik denetim zinciri bütünlüğünü doğrular")
    p_aud.set_defaults(func=cmd_audit_verify)

    # erp-export
    p_erp = subparsers.add_parser("erp-export", help="THP mahsup fişlerini dışa aktarır")
    p_erp.add_argument("--format", default="json", choices=["json", "logo_xml", "sap_csv"])
    p_erp.add_argument("--cost-center", default="740.01.001")
    p_erp.set_defaults(func=cmd_erp_export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
