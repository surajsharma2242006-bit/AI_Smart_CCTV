"""Consent-based face registration and recognition using the optional face_recognition package."""
from __future__ import annotations

import json
import re
import importlib
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from config import FACES_DIR
from database import add_face_profile, delete_face_profile, get_face_profiles


def _face_library():
    """Import the third-party package without colliding with this project's compatibility module."""
    project_root = Path(__file__).resolve().parent
    existing = sys.modules.get("face_recognition")
    if existing and Path(getattr(existing, "__file__", "")).resolve() != project_root / "face_recognition.py":
        return existing
    if existing:
        sys.modules.pop("face_recognition", None)
    original_path = sys.path[:]
    try:
        sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != project_root]
        return importlib.import_module("face_recognition")
    finally:
        sys.path = original_path


def library_available() -> bool:
    try:
        _face_library()
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip())[:60]


def register_face(name: str, image_bytes: bytes) -> tuple[bool, str]:
    if not name.strip():
        return False, "Enter a display name."
    if not library_available():
        return False, "Face recognition is unavailable. Install the optional face-recognition package."
    face_recognition = _face_library()
    raw = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        return False, "The uploaded image could not be read."
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb)
    if len(encodings) != 1:
        return False, "Use a clear photo containing exactly one face."
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"{_safe_name(name)}_{stamp}"
    image_path = FACES_DIR / f"{stem}.jpg"
    encoding_path = FACES_DIR / f"{stem}.npy"
    cv2.imwrite(str(image_path), image)
    np.save(encoding_path, encodings[0])
    add_face_profile(name.strip(), str(image_path), str(encoding_path))
    return True, "Face registered with documented consent."


def identify_faces(frame: np.ndarray) -> list[dict[str, object]]:
    if not library_available():
        return []
    face_recognition = _face_library()
    profiles = get_face_profiles()
    known_encodings, known_names = [], []
    for row in profiles.itertuples():
        path = Path(row.encoding_path)
        if path.exists():
            known_encodings.append(np.load(path))
            known_names.append(row.display_name)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)
    results: list[dict[str, object]] = []
    for location, encoding in zip(locations, encodings):
        name = "Unknown"
        if known_encodings:
            distances = face_recognition.face_distance(known_encodings, encoding)
            best = int(np.argmin(distances))
            if distances[best] < 0.48:
                name = known_names[best]
        results.append({"location": location, "name": name})
    return results


def erase_face_profile(profile_id: int) -> bool:
    """Delete the consent image and encoding, then deactivate its database record."""
    paths = delete_face_profile(profile_id)
    if not paths:
        return False
    for raw_path in paths:
        Path(raw_path).unlink(missing_ok=True)
    return True
