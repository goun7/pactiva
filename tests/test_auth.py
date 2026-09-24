"""
Pactiva Rol Tabanlı API Anahtarı Yetkilendirme Testleri (tests/test_auth.py)
"""

import pytest
from fastapi import HTTPException
from pactiva_core.auth import (
    get_current_user_context,
    DEFAULT_ADMIN_KEY,
    DEFAULT_AUDITOR_KEY,
)


def test_auth_context_unauthenticated_default():
    ctx = get_current_user_context(api_key=None)
    assert ctx["role"] == "employer"
    assert ctx["is_authenticated"] is False


def test_auth_context_valid_admin_key():
    ctx = get_current_user_context(api_key=DEFAULT_ADMIN_KEY)
    assert ctx["role"] == "admin"
    assert ctx["identity"] == "system_admin"
    assert ctx["is_authenticated"] is True


def test_auth_context_valid_auditor_key():
    ctx = get_current_user_context(api_key=DEFAULT_AUDITOR_KEY)
    assert ctx["role"] == "auditor"
    assert ctx["identity"] == "external_labor_auditor"
    assert ctx["is_authenticated"] is True


def test_auth_context_invalid_key_raises_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_context(api_key="completely_fake_invalid_key_123")
    assert exc.value.status_code == 401
    assert "Geçersiz API Anahtarı" in exc.value.detail
