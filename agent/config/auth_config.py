"""Super Admin authentication and database configuration.

IMPORTANT: Override these via environment variables or a `.env` file
at your project root before deploying. Do NOT hardcode real secrets here.

Environment variables honored (highest priority first):
  CRA_DATABASE_URL       - Postgres connection string (overrides DATABASE_URL)
  CRA_SUPER_ADMIN_EMAIL  - Super admin login email
  CRA_SUPER_ADMIN_PASSWORD - Super admin password
  CRA_FLOW_URL           - Power Automate webhook for reports
"""
import os

# Attempt to load .env file (optional dependency, silently skip if missing)
try:
    from pathlib import Path
    _env_path = Path.cwd() / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            # Do not override variables already set in the real environment
            if _k and _k not in os.environ:
                os.environ[_k] = _v
except Exception:
    pass

# ── Super Admin ─────────────────────────────────────────────────
SUPER_ADMIN_EMAIL = os.getenv("CRA_SUPER_ADMIN_EMAIL", "admin@example.com")
SUPER_ADMIN_PASSWORD = os.getenv("CRA_SUPER_ADMIN_PASSWORD", "admin123")

# ── Shared Cloud Database (Neon Postgres) ───────────────────────
# This is the default SHARED database used by the entire team.
# Individual developers can override by setting CRA_DATABASE_URL in their
# environment or a local `.env` file.
_DEFAULT_NEON_URL = (
    "postgresql://neondb_owner:npg_JmZTG6FwKpE7"
    "@ep-jolly-cloud-amn3kbk3.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require"
)
DATABASE_URL = os.getenv("CRA_DATABASE_URL", _DEFAULT_NEON_URL)

# ── Power Automate webhook (daily reports) ──────────────────────
CRA_FLOW_URL = os.getenv(
    "CRA_FLOW_URL",
    "https://defaultcff20d814abd4f219998f39afd1df6.2a.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/243a9a7a866c46dca7f63ba89b2feced/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=YOxpQhyv1jIB2Cc2UDF7bX4PEXz0BTKb0Nnl2Kw7_RI",
)
