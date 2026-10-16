"""
Pytest konfigürasyonu — PACTIVA-DB-IZOLASYONU (DALGA-C-2 BULGU).

Once: tests/test_cli.py subprocess'leri ve pactiva_core.api modül-importu
init_db()'yi DEFAULT_DB_PATH ('pactiva.db' — goreceli) ile cagiriyordu, bu
da her test-kosusunu CWD'ye (repo-rootu) YAZIYORDU: pactiva.db 901.120 B ->
929.792 B (tek koşuda buyudu, LEED olcumu).

Onemli: subprocess testleri env'i MIRAS alir; bu yuzden PACTIVA_DB_PATH
burada ayarlanirsa hem ana surec (in-process testler + api importu) hem de
subprocess'ler tmp'ye gider. Testleri CWD'den bagimsiz yapar.
"""

import os
import tempfile

_DB_TMP = tempfile.mkdtemp(prefix="pactiva-test-")
os.environ["PACTIVA_DB_PATH"] = os.path.join(_DB_TMP, "test.sqlite3")
