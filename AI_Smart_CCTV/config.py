"""Central configuration for the consent-first Smart CCTV application."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
# Streamlit Community Cloud has an ephemeral filesystem.  Keep all mutable data
# in one configurable location so production hosts can mount persistent storage
# without changing the application code.
DATA_DIR = Path(os.getenv("CCTV_DATA_DIR", str(BASE_DIR))).expanduser().resolve()
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DATABASE_DIR = DATA_DIR / "database"
FACES_DIR = DATA_DIR / "registered_faces"
MODELS_DIR = BASE_DIR / "models"

for directory in (SNAPSHOTS_DIR, DATABASE_DIR, FACES_DIR, MODELS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    database_path: Path = DATABASE_DIR / "smart_cctv.db"
    snapshot_cooldown_seconds: int = int(os.getenv("CCTV_SNAPSHOT_COOLDOWN", "30"))
    presence_seconds: int = int(os.getenv("CCTV_PRESENCE_SECONDS", "120"))
    motion_threshold: int = int(os.getenv("CCTV_MOTION_THRESHOLD", "1800"))
    smtp_host: str = os.getenv("CCTV_SMTP_HOST", "")
    smtp_port: int = int(os.getenv("CCTV_SMTP_PORT", "587"))
    smtp_username: str = os.getenv("CCTV_SMTP_USERNAME", "")
    smtp_password: str = os.getenv("CCTV_SMTP_PASSWORD", "")
    alert_recipient: str = os.getenv("CCTV_ALERT_RECIPIENT", "")
    # Set this to true for Streamlit Community Cloud and other hosted services.
    # Those servers do not have access to the viewer's laptop webcam.
    hosted_deployment: bool = os.getenv("CCTV_HOSTED_DEPLOYMENT", "false").lower() == "true"

    @property
    def email_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password and self.alert_recipient)


settings = Settings()
