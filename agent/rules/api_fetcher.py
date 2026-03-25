"""Fetches rules from a centralized remote rules API with local caching."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_DIR = Path.home() / ".cache" / "code_review_agent" / "remote_rules"
_CACHE_TTL_SECONDS = 3600  # 1 hour


class ApiFetcher:
    """Fetches and caches rules from a remote HTTP API.

    The API is expected to respond with a JSON body of the shape:
        {
          "version": "1.0",
          "rules": [ { ...rule dict... }, ... ]
        }

    Authentication is done via a Bearer token in the Authorization header.
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or os.getenv("REVIEW_RULES_API_TOKEN")

    def fetch_rules(
        self,
        language: str,
        framework: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch rules for the given language/framework from the remote API.

        Args:
            language: Language identifier (e.g. 'python').
            framework: Optional framework identifier.
            use_cache: Whether to use a local file cache.

        Returns:
            List of rule dictionaries, or [] if the fetch fails.
        """
        cache_key = self._cache_key(language, framework)
        cache_path = _CACHE_DIR / f"{cache_key}.json"

        if use_cache and self._is_cache_valid(cache_path):
            logger.debug("Using cached remote rules from %s", cache_path)
            return self._load_cache(cache_path)

        rules = self._do_fetch(language, framework)
        if rules and use_cache:
            self._save_cache(cache_path, rules)
        return rules

    def _do_fetch(self, language: str, framework: Optional[str]) -> List[Dict[str, Any]]:
        """Perform the actual HTTP request."""
        try:
            import urllib.request
            import urllib.error

            params = f"language={language}"
            if framework:
                params += f"&framework={framework}"
            url = f"{self.base_url}/rules?{params}"

            req = urllib.request.Request(url)
            if self.token:
                req.add_header("Authorization", f"Bearer {self.token}")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "CodeReviewAgent/1.0")

            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                data: Dict[str, Any] = json.loads(body)
                rules = data.get("rules", [])
                logger.info("Fetched %d remote rules for %s/%s", len(rules), language, framework)
                return rules

        except Exception as exc:
            logger.warning("Failed to fetch remote rules: %s", exc)
            return []

    @staticmethod
    def _cache_key(language: str, framework: Optional[str]) -> str:
        raw = f"{language}_{framework or 'none'}"
        return hashlib.md5(raw.encode()).hexdigest()[:12] + f"_{language}"

    @staticmethod
    def _is_cache_valid(cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        age = time.time() - cache_path.stat().st_mtime
        return age < _CACHE_TTL_SECONDS

    @staticmethod
    def _load_cache(cache_path: Path) -> List[Dict[str, Any]]:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    @staticmethod
    def _save_cache(cache_path: Path, rules: List[Dict[str, Any]]) -> None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(rules, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Could not save rule cache: %s", exc)
