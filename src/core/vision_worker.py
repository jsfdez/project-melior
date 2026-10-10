import cv2
import mediapipe as mp
import numpy as np
import threading
import queue
import time
import os
import urllib.request
from typing import Optional
from src.core.contracts import VisionFrame, HeadPose

# Configuration
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_PATH = "face_landmarker.task"

def download_model():
    if not os.path.exists(MODEL_PATH):
        print(f"📥 Downloading MediaPipe model from {MODEL_URL}...")
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print("✅ Download complete.")
        except Exception as e:
            print(f"❌ Failed to download model: {e}")
            raise RuntimeError(f"Failed to download model: {e}")
    else:
        print("✅ Model file already exists.")

class VisionWorker(threading.Thread):
    def __init__(self, output_queue: queue.Queue):
        super().__init__()
        self.output_queue = output_queue
        self._stop_event = threading.Event()
        self.daemon = True  # Ensure thread dies when main program exits

        self.landmarker = None
        self.cap = None
        self.start_time = 0

    def stop(self):
        """Signal the thread to stop."""
        self._stop_event.set()

    def run(self):
        """The main loop of the vision worker."""
        try:
            download_model()
            self._setup()
            self._vision_loop()
        except Exception as e:
            print(f"❌ VisionWorker Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._shutdown()

    def _setup(self):
        print("⚙️  [VisionWorker] Setting up MediaPipe and Camera...")

        BaseOptions = mp.tasks.BaseOptions
        FaceLandmarker = mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1
        )
        self.landmarker = FaceLandmarker.create_from_options(options)

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("❌ Error: Could not open webcam.")

        self.start_time = time.time()
        print("✅ [VisionWorker] Setup complete.")

    def _vision_loop(self):
        print("👁️  [VisionWorker] Vision Loop Started")

        while not self._stop_event.is_set():
            success, frame = self.cap.read()
            if not success:
                time.sleep(0.1)
                continue

            # Convert BGR to RGB for MediaPipe
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

            # Timestamp in ms for VIDEO mode
            timestamp_ms = int((time.time() - self.start_time) * 1000)

            # Detect landmarks
            detection_result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

            # Placeholder for head pose (to be implemented in a future step)
            head_pose = HeadPose(pitch=0.0, yaw=0.0, roll=0.0)

            # Extract landmarks (if any)
            landmarks = None
            if detection_result.face_landmarks:
                # For simplicity, we'll just store the raw landmark list
                landmarks = detection_result.face_landmarks

            # Create the VisionFrame object
            vision_frame = VisionFrame(
                timestamp=time.time(),
                head_pose=head_pose,
                landmarks=landmarks,
                frame=frame
            )

            # Put in queue (non-blocking to avoid stalling the vision loop if UI is slow)
            try:
                self.output_queue.put_nowait(vision_frame)
            except queue.Full:
                pass # Drop frame if queue is full

            # Small sleep to prevent hogging CPU if frame processing is too fast
            time.sleep(0.01)

    def _shutdown(self):
        print("🛑 [VisionWorker] Shutting down...")
        if self.cap:
            self.cap.release()
        if self.landmarker:
            self.landmarker.close()
        print("✅ [VisionWorker] Shutdown complete.")
