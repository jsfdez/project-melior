"""Live demo of head tracking + gestures. Esc quits, R recalibrates the neutral pose.

    python demo_gestures.py [camera_index]
"""
import sys

import cv2

from src.interaction.gesture_engine import GestureEngine
from src.vision.head_tracker import HeadTracker

GREEN, YELLOW, RED = (0, 255, 0), (0, 255, 255), (0, 0, 255)


def draw_text(frame, text, y, color=GREEN):
    cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def main():
    cam = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    engine = GestureEngine()
    log = []
    with HeadTracker(cam) as tracker:
        while True:
            frame, vf = tracker.read()
            if frame is None:
                print("No camera frame")
                break
            for ev in engine.update(vf):
                msg = f"{ev.event_type} {ev.target_id or ''}".strip()
                print(msg)
                log = (log + [msg])[-4:]

            frame = cv2.flip(frame, 1)  # mirror for display only
            h, w = frame.shape[:2]
            dy, dp = engine.deviation()
            if not engine.calibrated:
                draw_text(frame, "Hold still, looking at the screen: calibrating...", 30, YELLOW)
            else:
                draw_text(frame, f"yaw {dy:+.1f}  pitch {dp:+.1f}   (R = recalibrate)", 30)
                draw_text(frame, f"pointing: {engine.current or '-'}", 60, YELLOW)
                # dwell progress bar: fills while the head is still on an option
                cv2.rectangle(frame, (10, 75), (210, 95), (80, 80, 80), 1)
                cv2.rectangle(frame, (10, 75), (10 + int(200 * engine.dwell_progress), 95), GREEN, -1)
            draw_text(frame, f"blink {vf.blink:.2f}" if vf else "No face", 120, RED if not vf else GREEN)
            for i, msg in enumerate(reversed(log)):
                draw_text(frame, msg, h - 20 - 28 * i, YELLOW)
            cv2.imshow("Melior gestures", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            if key in (ord("r"), ord("R")):
                engine.recalibrate()
                log = []
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
