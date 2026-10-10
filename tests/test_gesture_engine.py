import unittest

from src.core.contracts import HeadPose, VisionFrame
from src.interaction.gesture_engine import GestureConfig, GestureEngine

# Default signs are inverted for the camera: positive raw yaw = "left", positive raw pitch = "down".


def vf(t, yaw=0.0, pitch=0.0, blink=0.0):
    return VisionFrame(timestamp=t, head_pose=HeadPose(pitch=pitch, yaw=yaw, roll=0.0), blink=blink)


class Sim:
    """Feeds frames at 20 fps and collects events."""

    def __init__(self):
        self.e = GestureEngine(GestureConfig(smoothing=1.0))
        self.t = 0.0
        self.events = []
        while not self.e.calibrated:
            self.step()

    def step(self, **kw):
        self.t += 0.05
        self.events += self.e.update(vf(self.t, **kw))

    def hold(self, seconds, **kw):
        for _ in range(round(seconds / 0.05)):
            self.step(**kw)

    def kinds(self):
        return [(x.event_type, x.target_id) for x in self.events]


class GestureEngineTest(unittest.TestCase):
    def test_no_events_while_calibrating(self):
        e = GestureEngine()
        self.assertEqual(e.update(vf(0.0, yaw=30)), [])

    def test_small_jitter_ignored(self):
        s = Sim()
        s.hold(2, yaw=2, pitch=1.5)
        self.assertEqual(s.events, [])

    def test_brief_pass_does_not_highlight(self):
        s = Sim()
        s.hold(0.2, yaw=10)  # shorter than stable_s
        s.hold(1, yaw=0)
        self.assertEqual(s.events, [])

    def test_stable_direction_highlights_then_dwell_selects(self):
        s = Sim()
        s.hold(0.6, yaw=10)
        self.assertEqual(s.kinds(), [("move", "left")])
        s.hold(2.0, yaw=10)
        self.assertEqual(s.kinds(), [("move", "left"), ("dwell", "left")])

    def test_sign_convention(self):
        for kw, name in [({"yaw": -10}, "right"), ({"pitch": 10}, "down"), ({"pitch": -10}, "up")]:
            s = Sim()
            s.hold(0.6, **kw)
            self.assertEqual(s.kinds(), [("move", name)], kw)

    def test_dwell_fires_once_until_return_to_center(self):
        s = Sim()
        s.hold(4, yaw=10)
        self.assertEqual([k for k, _ in s.kinds()].count("dwell"), 1)
        s.hold(1, yaw=0)
        s.hold(3, yaw=-10)
        self.assertEqual(s.kinds()[-2:], [("move", "right"), ("dwell", "right")])

    def test_moving_resets_dwell(self):
        s = Sim()
        s.hold(0.6, yaw=10)
        s.hold(0.8, yaw=10)
        s.hold(0.2, yaw=16)  # drift beyond still_deg restarts the timer
        s.hold(0.8, yaw=16)
        self.assertNotIn(("dwell", "left"), s.kinds())

    def test_short_blink_ignored_long_blink_goes_back(self):
        s = Sim()
        s.hold(0.2, blink=0.9)
        s.hold(0.2, blink=0.0)
        self.assertEqual(s.events, [])
        s.hold(1.0, blink=0.9)
        self.assertEqual(s.kinds(), [("back", None)])

    def test_face_lost_returns_nothing(self):
        s = Sim()
        self.assertEqual(s.e.update(None), [])


if __name__ == "__main__":
    unittest.main()
