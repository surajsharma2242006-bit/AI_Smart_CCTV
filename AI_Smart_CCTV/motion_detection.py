"""Transparent motion and rule evaluation helpers; motion is not a threat verdict."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np


@dataclass
class MotionResult:
    motion_detected: bool
    changed_pixels: int
    contour_count: int


class MotionDetector:
    def __init__(self, minimum_area: int = 1800) -> None:
        self.minimum_area = minimum_area
        self.previous_gray: np.ndarray | None = None

    def analyse(self, frame: np.ndarray) -> MotionResult:
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0)
        if self.previous_gray is None:
            self.previous_gray = gray
            return MotionResult(False, 0, 0)
        delta = cv2.absdiff(self.previous_gray, gray)
        self.previous_gray = gray
        threshold = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        threshold = cv2.dilate(threshold, None, iterations=2)
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        meaningful = [c for c in contours if cv2.contourArea(c) >= self.minimum_area]
        changed = sum(int(cv2.contourArea(c)) for c in meaningful)
        return MotionResult(bool(meaningful), changed, len(meaningful))


class PresenceTracker:
    def __init__(self) -> None:
        self.first_seen: datetime | None = None

    def update(self, people_count: int) -> int:
        if people_count:
            self.first_seen = self.first_seen or datetime.now()
            return int((datetime.now() - self.first_seen).total_seconds())
        self.first_seen = None
        return 0
