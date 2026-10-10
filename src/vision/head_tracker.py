"""Head tracking with MediaPipe Face Landmarker (Python).

Turns webcam frames into `VisionFrame`s (head pose + blink score).
Video never leaves this process.
"""
import math
import time
import urllib.request
import platform
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from src.core.contracts import HeadPose, VisionFrame


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "face_landmarker.task"


def ensure_model(path: Path = MODEL_PATH) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading face_landmarker.task to {path} ...")
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


def pose_from_matrix(m: np.ndarray) -> HeadPose:
    """4x4 facial transformation matrix -> pitch/yaw/roll in degrees."""
    r = np.asarray(m)[:3, :3]
    yaw = math.degrees(math.atan2(r[0, 2], r[2, 2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -r[1, 2]))))
    roll = math.degrees(math.atan2(r[1, 0], r[1, 1]))
    return HeadPose(pitch=pitch, yaw=yaw, roll=roll)


class HeadTracker:
    def __init__(self, camera_index: int = 0, model_path: Path = MODEL_PATH):
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model(model_path))),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

        # Use CAP_DSHOW only on Windows
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else 0
        self._cap = cv2.VideoCapture(camera_index, backend)
        self._t0 = time.monotonic()
        self._last_ts_ms = -1

    def read(self):
        """Returns (bgr_frame, VisionFrame | None). VisionFrame is None when no face is seen."""
        ok, frame = self._cap.read()
        if not ok:
            return None, None
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # detect_for_video requires strictly increasing timestamps
        ts_ms = max(int((time.monotonic() - self._t0) * 1000), self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)
        if not result.face_blendshapes or not result.facial_transformation_matrixes:
            return frame, None
        scores = {c.category_name: c.score for c in result.face_blendshapes[0]}
        blink = (scores.get("eyeBlinkLeft", 0.0) + scores.get("eyeBlinkRight", 0.0)) / 2
        return frame, VisionFrame(
            timestamp=ts_ms / 1000.0,
            head_pose=pose_from_matrix(result.facial_transformation_matrixes[0]),
            blink=blink,
            frame=frame
        )

    def close(self):
        self._cap.release()
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
