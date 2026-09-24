"""
Pactiva ERP ve Çift Taraflı Muhasebe Entegrasyonu Testleri (tests/test_erp_export.py)
"""

from decimal import Decimal
import xml.etree.ElementTree as ET
import pytest

from pactiva_core.erp_export import (
    generate_journal_entry,
    export_to_logo_xml,
    export_to_sap_csv,
)


def test_thp_double_entry_balance():
    # 740.01.001 (Brüt) = 360.01.010 (Stopaj) + 329.01.001 (Net)
    gross = Decimal("3000.00")
    tax = Decimal("300.00")
    net = Decimal("2700.00")

    entry = generate_journal_entry(
        shift_id="shift_test_12345678",
        worker_name="Ahmet Yılmaz",
        project_title="Maslak Stüdyo Çekimi",
        gross_amount=gross,
        withholding_tax=tax,
        net_payout=net,
        account_cost_center="740.01.001",
    )

    assert entry["is_balanced"] is True
    assert entry["total_debit"] == gross
    assert entry["total_credit"] == tax + net
    assert len(entry["lines"]) == 3

    # Borç satırı
    debit_line = entry["lines"][0]
    assert debit_line["account_code"] == "740.01.001"
    assert debit_line["debit"] == gross
    assert debit_line["credit"] == Decimal("0.00")

    # Alacak satırı 1 (Stopaj)
    tax_line = entry["lines"][1]
    assert tax_line["account_code"] == "360.01.010"
    assert tax_line["credit"] == tax

    # Alacak satırı 2 (Net hak ediş)
    net_line = entry["lines"][2]
    assert net_line["account_code"] == "329.01.001"
    assert net_line["credit"] == net


def test_logo_xml_structure():
    gross = Decimal("5000.00")
    tax = Decimal("500.00")
    net = Decimal("4500.00")

    entry = generate_journal_entry(
        shift_id="shift_logo_abc",
        worker_name="Mehmet Demir",
        project_title="Kuzey Marmara Şantiye",
        gross_amount=gross,
        withholding_tax=tax,
        net_payout=net,
    )

    xml_output = export_to_logo_xml([entry])
    assert "<?xml version=" in xml_output
    assert "<TRANSACTIONS>" in xml_output
    assert "<GL_VOUCHER" in xml_output
    assert "<GL_CODE>740.01.001</GL_CODE>" in xml_output
    assert "<GL_CODE>360.01.010</GL_CODE>" in xml_output
    assert "<GL_CODE>329.01.001</GL_CODE>" in xml_output

    # XML sözdizimini doğrula
    root = ET.fromstring(xml_output)
    assert root.tag == "TRANSACTIONS"
    vouchers = root.findall(".//GL_VOUCHER")
    assert len(vouchers) == 1
    trans = vouchers[0].findall(".//TRANSACTION")
    assert len(trans) == 3


def test_sap_csv_format():
    entry = generate_journal_entry(
        shift_id="shift_sap_xyz",
        worker_name="Ayşe Kaya",
        project_title="Lojistik Dağıtım",
        gross_amount=Decimal("1200.00"),
        withholding_tax=Decimal("120.00"),
        net_payout=Decimal("1080.00"),
    )

    csv_output = export_to_sap_csv([entry])
    lines = csv_output.strip().split("\n")
    assert len(lines) == 4  # 1 Başlık + 3 Mahsup Kalemi

    header = lines[0]
    assert "POSTING_DATE;DOCUMENT_TYPE;ACCOUNT_CODE;DEBIT_AMOUNT;CREDIT_AMOUNT;CURRENCY" in header

    debit_row = lines[1].split(";")
    assert debit_row[1] == "SA"
    assert debit_row[2] == "740.01.001"
    assert debit_row[3] == "1200.00"
    assert debit_row[5] == "TRY"
