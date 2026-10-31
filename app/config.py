"""Configuration and environment variables for Vaari."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present
ROOT_DIR = Path(__file__).parent.parent.resolve()
load_dotenv(ROOT_DIR / ".env")


VALID_ENVS = ("development", "production")


class Settings:
    @property
    def env(self) -> str:
        """VAARI_ENV: 'development' (default) or 'production'."""
        return os.environ.get("VAARI_ENV", "development").strip().lower() or "development"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def allow_hosted_reader_in_production(self) -> bool:
        """Explicit override needed before the hosted reader may run in production."""
        return os.environ.get("VAARI_ALLOW_HOSTED_READER_IN_PRODUCTION", "false").strip().lower() in (
            "true",
            "1",
        )

    @property
    def secret_key(self) -> str:
        """VAARI_SECRET_KEY signs login sessions. Required in production."""
        return os.environ.get("VAARI_SECRET_KEY", "").strip()

    @property
    def session_hours(self) -> float:
        return float(os.environ.get("VAARI_SESSION_HOURS", "12"))

    @property
    def auth_mode(self) -> str:
        """'passcode' in development (shared passcode and accounts both work), 'accounts' in production."""
        return "accounts" if self.is_production else "passcode"

    @property
    def login_rate_per_min(self) -> int:
        """Sign-in attempts allowed per client address per minute."""
        return int(os.environ.get("VAARI_LOGIN_RATE_PER_MIN", "10"))

    @property
    def login_lockout_failures(self) -> int:
        """Wrong passwords in a row (per username) before the username is locked."""
        return int(os.environ.get("VAARI_LOGIN_LOCKOUT_FAILURES", "5"))

    @property
    def login_lockout_minutes(self) -> float:
        return float(os.environ.get("VAARI_LOGIN_LOCKOUT_MINUTES", "15"))

    @property
    def google_api_key(self) -> str:
        """VAARI_GOOGLE_API_KEY: a Google Cloud API key with Speech-to-Text and/or Cloud Translation turned on.
        Used only by the server; it is never sent to a browser."""
        return os.environ.get("VAARI_GOOGLE_API_KEY", "").strip()

    @property
    def voice_speech(self) -> str:
        """VAARI_VOICE_SPEECH: 'google' (Google Cloud Speech-to-Text: Punjabi, Hindi and English in one go, works
        on every browser), 'browser' (the browser's own speech recognition) or 'auto' (default: google when a key
        is set, else browser)."""
        v = os.environ.get("VAARI_VOICE_SPEECH", "auto").strip().lower()
        if v not in ("google", "browser", "auto"):
            v = "auto"
        if v == "auto":
            return "google" if self.google_api_key else "browser"
        return v

    @property
    def voice_translate(self) -> bool:
        """VAARI_VOICE_TRANSLATE: when the app's own rules cannot read an answer, ask Google Translate for an
        English version and try again (default true when a key is set). Never used for phone numbers."""
        default = "true" if self.google_api_key else "false"
        return os.environ.get("VAARI_VOICE_TRANSLATE", default).strip().lower() in ("true", "1", "yes")

    @property
    def voice_rate_per_min(self) -> int:
        """Spoken answers sent to speech-to-text per client address per minute."""
        return int(os.environ.get("VAARI_VOICE_RATE_PER_MIN", "60"))

    @property
    def upload_rate_per_min(self) -> int:
        """Photo uploads (register pages, start and done photos) per client address per minute."""
        return int(os.environ.get("VAARI_UPLOAD_RATE_PER_MIN", "30"))

    @property
    def trust_proxy(self) -> bool:
        """Use the first X-Forwarded-For address as the client (only behind your own reverse proxy)."""
        return os.environ.get("VAARI_TRUST_PROXY", "false").strip().lower() in ("true", "1")

    @property
    def driver_link_days(self) -> float:
        """Days a new driver link (machine token) stays valid."""
        return float(os.environ.get("VAARI_DRIVER_LINK_DAYS", "30"))

    @property
    def record_link_days(self) -> float:
        """Days a new service-record link stays valid."""
        return float(os.environ.get("VAARI_RECORD_LINK_DAYS", "365"))

    @property
    def cors_origins(self) -> list[str]:
        """Exact origins allowed to call the API from another site. Empty = same origin only."""
        raw = os.environ.get("VAARI_CORS_ORIGINS", "").strip()
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]

    @property
    def photo_store(self) -> str:
        """Where photos are kept: 'local' (VAARI_DATA_DIR). 's3' is planned, not built."""
        return os.environ.get("VAARI_PHOTO_STORE", "local").strip().lower() or "local"

    @property
    def backup_dir(self) -> str:
        """Where `python tasks.py backup` writes. Copy it off the machine too (see docs/DEPLOY.md)."""
        return os.environ.get("VAARI_BACKUP_DIR", "backups")

    @property
    def demo_passcode(self) -> str:
        return os.environ.get("VAARI_DEMO_PASSCODE", "change-me")

    @property
    def db_path(self) -> str:
        return os.environ.get("VAARI_DB_PATH", "data/vaari.sqlite")

    @property
    def data_dir(self) -> str:
        return os.environ.get("VAARI_DATA_DIR", "data")

    @property
    def tz(self) -> str:
        return os.environ.get("VAARI_TZ", "Asia/Kolkata")

    @property
    def today(self) -> str | None:
        val = os.environ.get("VAARI_TODAY", "").strip()
        return val if val else None

    @property
    def window_days(self) -> int:
        return int(os.environ.get("VAARI_WINDOW_DAYS", "20"))

    @property
    def max_radius_km(self) -> float:
        return float(os.environ.get("VAARI_MAX_RADIUS_KM", "25"))

    @property
    def road_factor(self) -> float:
        return float(os.environ.get("VAARI_ROAD_FACTOR", "1.3"))

    @property
    def max_photo_mb(self) -> float:
        return float(os.environ.get("VAARI_MAX_PHOTO_MB", "8"))

    @property
    def too_fast_min_per_acre(self) -> int:
        return int(os.environ.get("VAARI_TOO_FAST_MIN_PER_ACRE", "25"))

    @property
    def seed_phones(self) -> list[str]:
        raw = os.environ.get("VAARI_SEED_PHONES", "").strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def demo_plot_lat(self) -> float:
        return float(os.environ.get("VAARI_DEMO_PLOT_LAT", str(self.centre_lat)))

    @property
    def demo_plot_lon(self) -> float:
        return float(os.environ.get("VAARI_DEMO_PLOT_LON", str(self.centre_lon)))

    @property
    def centre_lat(self) -> float:
        return float(os.environ.get("VAARI_CENTRE_LAT", "30.7333"))

    @property
    def centre_lon(self) -> float:
        return float(os.environ.get("VAARI_CENTRE_LON", "76.7794"))

    @property
    def centre_name(self) -> str:
        return os.environ.get("VAARI_CENTRE_NAME", "Kisan Seva Kendra Nabha")

    @property
    def centre_phone(self) -> str:
        return os.environ.get("VAARI_CENTRE_PHONE", "9876543210")

    @property
    def public_base_url(self) -> str:
        return os.environ.get("VAARI_PUBLIC_BASE_URL", "").rstrip("/")

    @property
    def reader(self) -> str:
        return os.environ.get("VAARI_READER", "mock")

    @property
    def allow_hosted_reader(self) -> bool:
        return os.environ.get("VAARI_ALLOW_HOSTED_READER", "false").lower() in ("true", "1")

    @property
    def vision_provider(self) -> str:
        return os.environ.get("VAARI_VISION_PROVIDER", "gemini")

    @property
    def vision_model(self) -> str:
        return os.environ.get("VAARI_VISION_MODEL", "")

    @property
    def reader_probe(self) -> bool:
        """Send one synthetic image through a remote reader at start-up (default on)."""
        return os.environ.get("VAARI_READER_PROBE", "true").strip().lower() in ("true", "1")

    @property
    def custom_reader_url(self) -> str:
        """Endpoint of a future custom reader (VAARI_READER=custom)."""
        return os.environ.get("VAARI_CUSTOM_READER_URL", "").strip()

    @property
    def custom_reader_token(self) -> str:
        return os.environ.get("VAARI_CUSTOM_READER_TOKEN", "").strip()

    @property
    def reader_timeout_s(self) -> int:
        return int(os.environ.get("VAARI_READER_TIMEOUT_S", "20"))

    # ── Notifications (pilot v0.4) ───────────────────────────────────────
    @property
    def notify_worker(self) -> bool:
        """Run the background sender inside the web server (default true)."""
        return os.environ.get("VAARI_NOTIFY_WORKER", "true").strip().lower() in ("true", "1", "yes")

    @property
    def notify_interval_s(self) -> float:
        return float(os.environ.get("VAARI_NOTIFY_INTERVAL_S", "5"))

    @property
    def farmer_link_days(self) -> float:
        """Days a farmer's app link (/farmer/<token>) stays valid: one season by default."""
        return float(os.environ.get("VAARI_FARMER_LINK_DAYS", "180"))

    @property
    def farmer_quiet_hours(self) -> tuple[int, int] | None:
        """Hours (local time) when farmers' phones are not woken by alerts, e.g. '21-7'. Empty turns it off.
        The message is still in the farmer's page at once; only the phone alert waits for morning."""
        raw = os.environ.get("VAARI_FARMER_QUIET_HOURS", "21-7").strip()
        if not raw:
            return None
        try:
            a, b = (int(x) for x in raw.split("-", 1))
        except ValueError:
            return None
        if not (0 <= a <= 23 and 0 <= b <= 23) or a == b:
            return None
        return a, b

    @property
    def vapid_public_key(self) -> str:
        return os.environ.get("VAARI_VAPID_PUBLIC_KEY", "").strip()

    @property
    def vapid_private_key(self) -> str:
        return os.environ.get("VAARI_VAPID_PRIVATE_KEY", "").strip()

    @property
    def vapid_subject(self) -> str:
        """Contact for push services: 'mailto:you@example.org' or an https URL."""
        return os.environ.get("VAARI_VAPID_SUBJECT", "").strip()

    @property
    def driver_digest_hour(self) -> int:
        """Local hour for the drivers' morning job list push (-1 turns it off)."""
        return int(os.environ.get("VAARI_DRIVER_DIGEST_HOUR", "6"))


settings = Settings()
