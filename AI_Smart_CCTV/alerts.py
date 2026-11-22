"""Alert creation, local snapshots and optional SMTP notification."""
from __future__ import annotations

import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import cv2
import numpy as np

from config import SNAPSHOTS_DIR, settings
from database import add_alert, add_event


def save_snapshot(frame: np.ndarray, event_type: str) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_type = "".join(c if c.isalnum() else "_" for c in event_type)[:40]
    path = SNAPSHOTS_DIR / f"{stamp}_{safe_type}.jpg"
    cv2.imwrite(str(path), frame)
    return str(path)


def send_email(subject: str, body: str, snapshot_path: str | None = None) -> tuple[bool, str]:
    if not settings.email_ready:
        return False, "Email is not configured. Event was still saved locally."
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_username
        message["To"] = settings.alert_recipient
        message.set_content(body)
        if snapshot_path and Path(snapshot_path).exists():
            message.add_attachment(Path(snapshot_path).read_bytes(), maintype="image", subtype="jpeg", filename=Path(snapshot_path).name)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True, "Email alert sent."
    except Exception as exc:
        return False, f"Email alert failed: {exc}"


def create_security_event(event_type: str, severity: str, message: str, frame: np.ndarray,
                          people_count: int, notify: bool) -> tuple[int, str, str]:
    snapshot_path = save_snapshot(frame, event_type)
    event_id = add_event(event_type, severity, message, people_count, snapshot_path)
    add_alert(event_id, event_type, severity, message, snapshot_path)
    email_status = "Email not requested."
    if notify:
        _, email_status = send_email(f"Smart CCTV: {event_type}", message, snapshot_path)
    return event_id, snapshot_path, email_status
