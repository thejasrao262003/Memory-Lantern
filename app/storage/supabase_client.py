"""Shared Supabase client for Memory Lantern storage.

Postgres holds the reaction log and story metadata; Supabase Storage holds the
generated assets (illustrations, narration, PDF). The client is created lazily
and cached, so the rest of the app stays importable without Supabase configured
(``supabase`` is imported only when a call actually needs it).

Required environment (HF Space secrets / .env):
    SUPABASE_URL   e.g. https://xxxx.supabase.co
    SUPABASE_KEY   the service-role key (server-side, bypasses RLS)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.utils.errors import StorageError

URL_ENV = "SUPABASE_URL"
KEY_ENV = "SUPABASE_KEY"

# Storage bucket for generated assets (create it as described in docs/STORAGE.md).
ASSET_BUCKET = "storybooks"


def is_configured() -> bool:
    """True if both Supabase env vars are present."""
    return bool(os.environ.get(URL_ENV) and os.environ.get(KEY_ENV))


@lru_cache(maxsize=1)
def get_client() -> Any:
    """Return a cached Supabase client, or raise :class:`StorageError` if unset."""
    url = os.environ.get(URL_ENV)
    key = os.environ.get(KEY_ENV)
    if not url or not key:
        raise StorageError(
            f"Supabase is not configured ({URL_ENV} / {KEY_ENV} missing)."
        )
    from supabase import create_client

    return create_client(url, key)
