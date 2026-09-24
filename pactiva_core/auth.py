"""
Pactiva — Rol Tabanlı Yetkilendirme ve API Anahtarı Koruması (pactiva_core/auth.py)
Kurumsal entegrasyonlar, denetçiler ve sistem rolleri için yetki kontrolü.
"""

import os
from typing import Any, Dict, Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

DEFAULT_ADMIN_KEY = os.environ.get("PACTIVA_ADMIN_KEY", "pactiva_adm_sec_999")
DEFAULT_AUDITOR_KEY = os.environ.get("PACTIVA_AUDITOR_KEY", "pactiva_aud_sec_555")

KNOWN_KEYS = {
    DEFAULT_ADMIN_KEY: {"role": "admin", "identity": "system_admin"},
    DEFAULT_AUDITOR_KEY: {"role": "auditor", "identity": "external_labor_auditor"},
}


def get_current_user_context(
    api_key: Optional[str] = Security(API_KEY_HEADER),
) -> Dict[str, Any]:
    """
    Gelen istekteki X-API-Key başlığını inceler ve rol bağlamını döner.
    Geliştirme veya açık uç noktalarda esnek varsayılan bağlam sağlar.
    """
    if not api_key:
        # Anahtar belirtilmemişse varsayılan yerel geliştirme bağlamı
        return {"role": "employer", "identity": "local_dev_user", "is_authenticated": False}

    if api_key in KNOWN_KEYS:
        ctx = dict(KNOWN_KEYS[api_key])
        ctx["is_authenticated"] = True
        return ctx

    # Geçersiz anahtar
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz API Anahtarı (X-API-Key). Yetkisiz erişim.",
    )
