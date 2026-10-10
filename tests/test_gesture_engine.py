import unittest

from src.core.contracts import HeadPose, VisionFrame
from src.interaction.gesture_engine import GestureConfig, GestureEngine


def vf(t, yaw=0.0, pitch=0.0, blink=0.0):
    return VisionFrame(timestamp=t, head_pose=HeadPose(pitch=pitch, yaw=yaw, roll=0.0), blink=blink)


def calibrated_engine():
    e = GestureEngine(GestureConfig(smoothing=1.0))
    t = 0.0
    while not e.calibrated:
        e.update(vf(t))
        t += 0.05
    return e, t


def kinds(events):
    return [(x.event_type, x.target_id) for x in events]


class GestureEngineTest(unittest.TestCase):
    def test_no_events_while_calibrating(self):
        e = GestureEngine()
        self.assertEqual(e.update(vf(0.0, yaw=30)), [])

    def test_move_fires_once_until_head_returns(self):
        e, t = calibrated_engine()
        evs = []
        for _ in range(10):  # head held to the side
            t += 0.1
            evs += e.update(vf(t, yaw=20))
        self.assertEqual(kinds(evs), [("move", "right")])
        for _ in range(3):  # back to neutral re-arms
            t += 0.1
            e.update(vf(t))
        t += 0.5
        self.assertEqual(kinds(e.update(vf(t, yaw=-20))), [("move", "left")])

    def test_vertical_moves(self):
        e, t = calibrated_engine()
        self.assertEqual(kinds(e.update(vf(t + 0.1, pitch=-20))), [("move", "down")])
        e, t = calibrated_engine()
        self.assertEqual(kinds(e.update(vf(t + 0.1, pitch=20))), [("move", "up")])

    def test_small_movement_ignored(self):
        e, t = calibrated_engine()
        self.assertEqual(e.update(vf(t + 0.1, yaw=5, pitch=4)), [])

    def test_short_blink_ignored_long_blink_goes_back(self):
        e, t = calibrated_engine()
        evs = []
        for _ in range(4):  # 0.2 s blink
            t += 0.05
            evs += e.update(vf(t, blink=0.9))
        t += 0.05
        e.update(vf(t, blink=0.0))
        self.assertEqual(evs, [])
        for _ in range(20):  # 1 s blink
            t += 0.05
            evs += e.update(vf(t, blink=0.9))
        self.assertEqual(kinds(evs), [("back", None)])

    def test_face_lost_returns_nothing(self):
        e, _ = calibrated_engine()
        self.assertEqual(e.update(None), [])


if __name__ == "__main__":
    unittest.main()
