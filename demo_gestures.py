"""Live demo of head tracking + gestures. Esc quits, R recalibrates the neutral pose.

    python demo_gestures.py [camera_index]
"""
import sys

import cv2

from src.interaction.gesture_engine import GestureEngine
from src.vision.head_tracker import HeadTracker


def main():
    cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    engine = GestureEngine()
    last = ""
    with HeadTracker(cam) as tracker:
        while True:
            frame, vf = tracker.read()
            if frame is None:
                print("No camera frame")
                break
            for ev in engine.update(vf):
                last = f"{ev.event_type} {ev.target_id or ''}".strip()
                print(last, f"(conf {ev.confidence:.2f})")

            frame = cv2.flip(frame, 1)  # mirror for display only
            dy, dp = engine.deviation()
            lines = [
                "Hold still: calibrating neutral pose..." if not engine.calibrated else f"yaw {dy:+.1f}  pitch {dp:+.1f}",
                f"blink {vf.blink:.2f}" if vf else "No face",
                f"last: {last}",
            ]
            for i, text in enumerate(lines):
                cv2.putText(frame, text, (10, 30 + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("Melior gestures", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            if key in (ord("r"), ord("R")):
                engine.recalibrate()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
