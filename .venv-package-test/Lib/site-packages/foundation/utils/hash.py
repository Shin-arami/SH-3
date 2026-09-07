# utils/hash.py

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from .json import normalize as json_normalize

# ----------------------------
# Core Hashing
# ----------------------------


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def md5(data: str) -> str:
    return hashlib.md5(data.encode("utf-8")).hexdigest()


def sha1(data: str) -> str:
    return hashlib.sha1(data.encode("utf-8")).hexdigest()


# ----------------------------
# Object Hashing (Deterministic)
# ----------------------------


def hash_object(obj: Any, algorithm: str = "sha256") -> str:
    normalized = json.dumps(json_normalize(obj), sort_keys=True, ensure_ascii=False)

    if algorithm == "md5":
        return md5(normalized)
    if algorithm == "sha1":
        return sha1(normalized)
    return sha256(normalized)


# ----------------------------
# Stable ID Generation
# ----------------------------


def stable_id(obj: Any, prefix: str = "") -> str:
    h = hash_object(obj)
    return f"{prefix}{h}" if prefix else h


def short_id(obj: Any, length: int = 12, prefix: str = "") -> str:
    h = hash_object(obj)
    short = h[:length]
    return f"{prefix}{short}" if prefix else short


# ----------------------------
# Nonce / Random IDs (non-deterministic)
# ----------------------------


def nonce() -> str:
    return hashlib.sha256(str(time.time_ns()).encode()).hexdigest()


def random_id(prefix: str = "", length: int = 16) -> str:
    base = nonce()[:length]
    return f"{prefix}{base}" if prefix else base


# ----------------------------
# Fingerprinting
# ----------------------------


def fingerprint(*values: Any, algorithm: str = "sha256") -> str:
    normalized = json.dumps(
        [json_normalize(v) for v in values],
        sort_keys=True,
        ensure_ascii=False,
    )

    if algorithm == "md5":
        return md5(normalized)
    if algorithm == "sha1":
        return sha1(normalized)
    return sha256(normalized)


# ----------------------------
# Cache Key Utilities
# ----------------------------


def cache_key(namespace: str, obj: Any) -> str:
    return f"{namespace}:{stable_id(obj)}"


def multi_key(namespace: str, *args: Any) -> str:
    return f"{namespace}:{fingerprint(*args)}"
