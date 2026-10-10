import cv2
import mediapipe as mp
import numpy as np
import os
import urllib.request
import time

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
            exit(1)
    else:
        print("✅ Model file already exists.")

def main():
    download_model()

    print("🚀 Initializing MediaPipe Face Landmarker (Tasks API)...")

    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.VIDEO,
        num_faces=1
    )

    try:
        with FaceLandmarker.create_from_options(options) as landmarker:
            print("📷 Opening webcam...")
            cap = cv2.VideoCapture(0)

            if not cap.isOpened():
                print("❌ Error: Could not open webcam.")
                return

            print("✅ Webcam opened. Press 'q' to quit.")

            # Track time for the video mode timestamping
            start_time = time.time()

            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    print("⚠️  Failed to grab frame")
                    break

                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)

                # MediaPipe Tasks API requires timestamp in milliseconds
                timestamp_ms = int((time.time() - start_time) * 1000)

                # Detect landmarks
                detection_result = landmarker.detect_for_video(mp_image, timestamp_ms)

                # Draw landmarks (Manual drawing to ensure compatibility)
                if detection_result.face_landmarks:
                    for face_landmarks in detection_result.face_landmarks:
                        for landmark in face_landmarks:
                            # landmark.x, landmark.y, landmark.z are normalized [0, 1]
                            h, w, _ = frame.shape
                            cx = int(landmark.x * w)
                            cy = int(landmark.y * h)
                            cv2.circle(frame, (cx, cy), 1, (0, 255, 0), -1)

                cv2.imshow('Melior - MediaPipe Tasks Test', frame)

                if cv2.waitKey(5) & 0xFF == ord('q'):
                    break

            cap.release()
            cv2.destroyAllWindows()
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
