from __future__ import annotations
import os
from functools import lru_cache
from supabase import create_client, Client


@lru_cache(maxsize=1)
def supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
