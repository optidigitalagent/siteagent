from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import unquote, urlsplit, urlunsplit


CLOUDFLARE_PROJECT_NAME_LIMIT = 58


def normalize_instagram_url(value: str) -> str:
    raw = value.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlsplit(raw)
    hostname = (parsed.hostname or "instagram.com").lower()
    if hostname == "www.instagram.com":
        hostname = "instagram.com"
    path_parts = [part for part in unquote(parsed.path).split("/") if part]
    normalized_path = "/" + "/".join(part.lower() for part in path_parts)
    return urlunsplit(("https", hostname, normalized_path.rstrip("/"), "", ""))


def stable_business_id(instagram_url: str, *, length: int = 16) -> str:
    normalized = normalize_instagram_url(instagram_url)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]


def cloudflare_project_name(prefix: str, instagram_url: str, *, collision: int = 0) -> str:
    normalized = normalize_instagram_url(instagram_url)
    handle = urlsplit(normalized).path.strip("/").split("/")[0] or "business"
    safe_prefix = _slug(prefix, fallback="siteagent")[:20]
    safe_handle = _slug(handle, fallback="business")[:24]
    stable_hash = stable_business_id(normalized, length=10)
    suffix = ""
    if collision:
        collision_hash = hashlib.sha256(
            f"{normalized}:{collision}".encode("utf-8")
        ).hexdigest()[:6]
        suffix = f"-{collision_hash}"
    hash_part = f"-{stable_hash}{suffix}"
    available = CLOUDFLARE_PROJECT_NAME_LIMIT - len(safe_prefix) - len(hash_part) - 1
    safe_handle = safe_handle[: max(1, available)].strip("-") or "business"
    return f"{safe_prefix}-{safe_handle}{hash_part}"[:CLOUDFLARE_PROJECT_NAME_LIMIT].strip("-")


def _slug(value: str, *, fallback: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or fallback
