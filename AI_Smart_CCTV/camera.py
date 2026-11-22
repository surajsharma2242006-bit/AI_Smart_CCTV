"""Local/IP camera lifecycle. No camera starts until an administrator presses Start."""
from __future__ import annotations

from typing import Union

import cv2
import numpy as np


class CameraManager:
    def __init__(self) -> None:
        self.capture: cv2.VideoCapture | None = None
        self.source: Union[int, str, None] = None

    def start(self, source: Union[int, str]) -> tuple[bool, str]:
        self.stop()
        self.capture = cv2.VideoCapture(source)
        self.source = source
        if not self.capture.isOpened():
            self.stop()
            return False, "Could not open this camera source. Check permissions, index, or stream URL."
        return True, "Camera started. The recording indicator is visible while frames are processed."

    def read(self) -> np.ndarray | None:
        if not self.capture or not self.capture.isOpened():
            return None
        ok, frame = self.capture.read()
        return frame if ok else None

    def stop(self) -> None:
        if self.capture:
            self.capture.release()
        self.capture = None
        self.source = None
