"""
Flask-Limiter singleton — imported by app.py to initialise and by route
modules to apply per-endpoint limits without creating a circular import.
"""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Storage URI: use Redis/Memcache in production (multi-worker safe).
# If RATELIMIT_STORAGE_URI is not set, falls back to in-memory (local dev only).
_storage_uri = os.environ.get('RATELIMIT_STORAGE_URI')

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # no app-wide default; limits are per-route only
    storage_uri=_storage_uri,   # None → in-memory fallback
    strategy='fixed-window',
)
