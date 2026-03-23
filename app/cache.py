import os
import time
import hashlib
import json
import logging
from pathlib import Path
from . import config

logger = logging.getLogger(__name__)


class FileCache:
    """File-based cache for proxied responses."""

    def __init__(self):
        self.cache_dir = Path(config.CACHE_DIR)
        if config.CACHE_ENABLED:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _make_key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def _meta_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.meta"

    def _data_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.data"

    def get(self, url: str, ttl: int) -> tuple[dict, bytes] | None:
        if not config.CACHE_ENABLED:
            return None

        key = self._make_key(url)
        meta_path = self._meta_path(key)
        data_path = self._data_path(key)

        if not meta_path.exists() or not data_path.exists():
            return None

        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)

            if time.time() - meta["timestamp"] > ttl:
                meta_path.unlink(missing_ok=True)
                data_path.unlink(missing_ok=True)
                return None

            with open(data_path, "rb") as f:
                data = f.read()

            return meta, data
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, url: str, meta: dict, data: bytes):
        if not config.CACHE_ENABLED:
            return

        key = self._make_key(url)

        try:
            meta["timestamp"] = time.time()
            with open(self._meta_path(key), "w") as f:
                json.dump(meta, f)
            with open(self._data_path(key), "wb") as f:
                f.write(data)
        except OSError as e:
            logger.warning(f"Cache write error: {e}")

    def clear(self):
        """Clear all cache files."""
        if self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                f.unlink(missing_ok=True)


cache = FileCache()
