import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Optional


def build_cache_key(scope: str, *parts: Any) -> str:
    serialized_parts = []
    for part in parts:
        try:
            serialized_parts.append(json.dumps(part, sort_keys=True, default=str))
        except TypeError:
            serialized_parts.append(str(part))

    content = "\n".join([str(scope), *serialized_parts])
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"{scope}:{digest}"


@dataclass
class CacheEntry:
    value: Any
    expires_at: Optional[float] = None


class InMemoryCache:
    def __init__(self, max_entries: Optional[int] = None, default_ttl_seconds: Optional[float] = None):
        self._entries = OrderedDict()
        self._max_entries = max_entries if max_entries is None else max(1, int(max_entries))
        self._default_ttl_seconds = default_ttl_seconds
        if default_ttl_seconds is not None:
            self._default_ttl_seconds = max(0.0, float(default_ttl_seconds))

    def _get_expiration_time(self, ttl_seconds: Optional[float]) -> Optional[float]:
        effective_ttl_seconds = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if effective_ttl_seconds is None:
            return None
        return time.time() + max(0.0, float(effective_ttl_seconds))

    @staticmethod
    def _is_expired(entry: CacheEntry) -> bool:
        return entry.expires_at is not None and entry.expires_at <= time.time()

    def _purge_expired(self):
        expired_keys = [key for key, entry in self._entries.items() if self._is_expired(entry)]
        for key in expired_keys:
            self._entries.pop(key, None)

    def _enforce_size_limit(self):
        if self._max_entries is None:
            return
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def get(self, key, default=None):
        self._purge_expired()
        entry = self._entries.get(key)
        if entry is None:
            return default

        self._entries.move_to_end(key)
        return entry.value

    def set(self, key, value, ttl_seconds: Optional[float] = None):
        self._entries[key] = CacheEntry(value=value, expires_at=self._get_expiration_time(ttl_seconds))
        self._entries.move_to_end(key)
        self._enforce_size_limit()
        return value

    def get_or_set(self, key, factory: Callable[[], Any], ttl_seconds: Optional[float] = None):
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value

        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def delete(self, key):
        self._entries.pop(key, None)

    def clear(self):
        self._entries.clear()

    def __len__(self):
        self._purge_expired()
        return len(self._entries)