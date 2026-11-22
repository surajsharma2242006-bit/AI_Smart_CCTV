"""YOLO person detector with an explicit, safe unavailable state."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from config import MODELS_DIR


class PersonDetector:
    def __init__(self, confidence: float = 0.45) -> None:
        self.confidence = confidence
        self.model: Any | None = None
        self.error: str | None = None

    def load(self) -> bool:
        if self.model is not None:
            return True
        try:
            from ultralytics import YOLO # type: ignore
            local_model = MODELS_DIR / "yolo11n.pt"
            self.model = YOLO(str(local_model if local_model.exists() else "yolo11n.pt"))
            return True
        except Exception as exc:  # dependency/model/network conditions are shown to the administrator
            self.error = f"YOLO is unavailable: {exc}"
            return False

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict[str, float]]]:
        annotated = frame.copy()
        if not self.load():
            cv2.putText(annotated, "YOLO unavailable - see status", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            return annotated, []
        result = self.model(frame, classes=[0], conf=self.confidence, verbose=False)[0]
        people: list[dict[str, float]] = []
        for box in result.boxes:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            confidence = float(box.conf[0])
            people.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": confidence})
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (66, 209, 245), 2)
            cv2.putText(annotated, f"Person {confidence:.0%}", (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (66, 209, 245), 2)
        return annotated, people


def point_in_zone(box: dict[str, float], zone: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = zone
    center_x = (box["x1"] + box["x2"]) / 2
    center_y = (box["y1"] + box["y2"]) / 2
    return x1 <= center_x <= x2 and y1 <= center_y <= y2
