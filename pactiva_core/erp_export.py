"""
Pactiva — Kurumsal ERP ve Muhasebe Entegrasyon Motoru (pactiva_core/erp_export.py)
Tekdüzen Hesap Planı (THP) uyumlu Logo, Mikro, SAP ve Zirve muhasebe mahsup fişi dışa aktarımı.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from pactiva_core.math_models import TWO_PLACES


def generate_journal_entry(
    shift_id: str,
    worker_name: str,
    project_title: str,
    gross_amount: Decimal,
    withholding_tax: Decimal,
    net_payout: Decimal,
    account_cost_center: str = "740.01.001",  # Hizmet Üretim Maliyeti
) -> Dict[str, Any]:
    """
    Tekdüzen Hesap Planına (THP) uygun çift taraflı muhasebe mahsup kaydını üretir.
    Borç: 740/770 (Brüt), Alacak: 360 (Stopaj), Alacak: 329/335 (Net Emanet Hak Ediş).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    journal_lines = [
        {
            "account_code": account_cost_center,
            "account_name": f"Dış Kaynak Saha/Set Hizmet Maliyeti ({project_title})",
            "debit": gross_amount,
            "credit": Decimal("0.00"),
            "description": f"Hak Ediş Brüt Tahakkuku - {worker_name}",
        },
        {
            "account_code": "360.01.010",
            "account_name": "Ödenecek Gelir Vergisi Stopajı (GVK Md. 94 %10)",
            "debit": Decimal("0.00"),
            "credit": withholding_tax,
            "description": f"GVK 94 Tevkifat Kesintisi - Shift #{shift_id[:8]}",
        },
        {
            "account_code": "329.01.001",
            "account_name": "Pactiva Akıllı Emanet Kasası Serbest Hak Edişleri",
            "debit": Decimal("0.00"),
            "credit": net_payout,
            "description": f"Net Hak Ediş Ödemesi - {worker_name}",
        },
    ]

    return {
        "date": now,
        "shift_id": shift_id,
        "document_type": "MAHSUP_FISI",
        "total_debit": gross_amount,
        "total_credit": (withholding_tax + net_payout).quantize(TWO_PLACES),
        "is_balanced": gross_amount == (withholding_tax + net_payout).quantize(TWO_PLACES),
        "lines": journal_lines,
    }


def export_to_logo_xml(entries: List[Dict[str, Any]]) -> str:
    """Logo Go / Tiger muhasebe programı uyumlu XML fiş dökümü üretir."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    xml_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<TRANSACTIONS>',
        '  <GL_VOUCHERS>',
    ]

    for idx, entry in enumerate(entries, 1):
        xml_lines.append(f'    <GL_VOUCHER DBOP="INS">')
        xml_lines.append(f'      <NUMBER>PACTIVA-{now_str}-{idx:04d}</NUMBER>')
        xml_lines.append(f'      <DATE>{entry["date"]}</DATE>')
        xml_lines.append(f'      <TYPE>4</TYPE>')  # 4 = Mahsup Fişi
        xml_lines.append(f'      <NOTES1>Pactiva Otonom Hak Edis Fisi</NOTES1>')
        xml_lines.append('      <TRANSACTIONS>')
        for line_no, line in enumerate(entry["lines"], 1):
            xml_lines.append('        <TRANSACTION>')
            xml_lines.append(f'          <GL_CODE>{escape(line["account_code"])}</GL_CODE>')
            xml_lines.append(f'          <DESCRIPTION>{escape(line["description"])}</DESCRIPTION>')
            sign = "0" if line["debit"] > Decimal("0.00") else "1"
            amount = line["debit"] if line["debit"] > Decimal("0.00") else line["credit"]
            xml_lines.append(f'          <SIGN>{sign}</SIGN>')
            xml_lines.append(f'          <AMOUNT>{amount}</AMOUNT>')
            xml_lines.append('        </TRANSACTION>')
        xml_lines.append('      </TRANSACTIONS>')
        xml_lines.append('    </GL_VOUCHER>')

    xml_lines.append('  </GL_VOUCHERS>')
    xml_lines.append('</TRANSACTIONS>')
    return "\n".join(xml_lines)


def export_to_sap_csv(entries: List[Dict[str, Any]]) -> str:
    """SAP HCM / FI muhasebe modülü uyumlu CSV bordro tahakkuk dökümü üretir."""
    header = "POSTING_DATE;DOCUMENT_TYPE;ACCOUNT_CODE;DEBIT_AMOUNT;CREDIT_AMOUNT;CURRENCY;LINE_TEXT;REFERENCE"
    csv_rows = [header]

    for entry in entries:
        for line in entry["lines"]:
            row = (
                f"{entry['date']};"
                f"SA;"  # G/L Account Document
                f"{line['account_code']};"
                f"{line['debit']};"
                f"{line['credit']};"
                f"TRY;"
                f"{line['description']};"
                f"SHIFT-{entry['shift_id'][:8]}"
            )
            csv_rows.append(row)

    return "\n".join(csv_rows)
