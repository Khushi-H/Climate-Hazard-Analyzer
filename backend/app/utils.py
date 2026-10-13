import math
import re
import unicodedata

import numpy as np


def to_native(o):
    """Recursively convert numpy types to plain Python, and NaN/inf to None (JSON + BSON safe)."""
    if isinstance(o, dict):
        return {str(k): to_native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_native(v) for v in o]
    if isinstance(o, np.ndarray):
        return [to_native(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


_CTRL = re.compile(r"[\x00-\x1f\x7f<>]")


def clean_label(name, fallback="Selected region") -> str:
    """User supplied labels are display-only, but still strip control chars and markup."""
    if not name:
        return fallback
    s = _CTRL.sub("", str(name))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80] or fallback


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:40] or "region"
