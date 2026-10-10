"""Gesture engine: VisionFrame -> GestureEvent. No UI, no LLM, no TTS.

Events emitted (GestureEvent.event_type):
  "move"  target_id = "left" | "right" | "up" | "down"  (head turned/tilted away from neutral)
  "back"  long blink (go back / cancel)

Neutral pose is learned automatically from the first frames; call `recalibrate()` to redo it.
"""
from dataclasses import dataclass
from typing import List, Optional

from src.core.contracts import GestureEvent, VisionFrame


@dataclass
class GestureConfig:
    yaw_deg: float = 12.0          # turn needed to trigger left/right
    pitch_deg: float = 9.0         # tilt needed to trigger up/down
    release_ratio: float = 0.5     # must return below this fraction of the threshold to re-arm
    move_cooldown_s: float = 0.35
    blink_threshold: float = 0.5   # eyeBlink score (0..1)
    blink_hold_s: float = 0.6      # a natural blink is ~0.1-0.4 s
    back_cooldown_s: float = 1.5
    neutral_seconds: float = 1.5
    smoothing: float = 0.5         # EMA factor, 1 = no smoothing
    # Flip if left/right or up/down come out inverted on your camera
    yaw_sign: int = 1
    pitch_sign: int = 1


class GestureEngine:
    def __init__(self, config: Optional[GestureConfig] = None):
        self.cfg = config or GestureConfig()
        self.recalibrate()

    def recalibrate(self):
        self._samples: List[tuple] = []
        self._t_start: Optional[float] = None
        self.neutral: Optional[tuple] = None  # (yaw, pitch)
        self._yaw = self._pitch = None
        self._armed = True
        self._last_move = -1e9
        self._blink_since: Optional[float] = None
        self._last_back = -1e9

    @property
    def calibrated(self) -> bool:
        return self.neutral is not None

    def deviation(self) -> tuple:
        """Smoothed (yaw, pitch) relative to neutral, for overlays/debug."""
        if self.neutral is None or self._yaw is None:
            return 0.0, 0.0
        return (self._yaw - self.neutral[0]) * self.cfg.yaw_sign, (self._pitch - self.neutral[1]) * self.cfg.pitch_sign

    def update(self, frame: Optional[VisionFrame]) -> List[GestureEvent]:
        c = self.cfg
        if frame is None:  # face lost: reset transient state
            self._armed = True
            self._blink_since = None
            return []
        t = frame.timestamp
        yaw, pitch = frame.head_pose.yaw, frame.head_pose.pitch

        if self.neutral is None:
            self._t_start = self._t_start if self._t_start is not None else t
            self._samples.append((yaw, pitch))
            if t - self._t_start >= c.neutral_seconds:
                ys, ps = zip(*self._samples)
                self.neutral = (sorted(ys)[len(ys) // 2], sorted(ps)[len(ps) // 2])
                self._yaw, self._pitch = self.neutral
            return []

        a = c.smoothing
        self._yaw = yaw if self._yaw is None else a * yaw + (1 - a) * self._yaw
        self._pitch = pitch if self._pitch is None else a * pitch + (1 - a) * self._pitch

        events: List[GestureEvent] = []
        dy, dp = self.deviation()
        ry, rp = abs(dy) / c.yaw_deg, abs(dp) / c.pitch_deg  # 1.0 = exactly at threshold

        if max(ry, rp) < c.release_ratio:
            self._armed = True
        elif self._armed and max(ry, rp) >= 1.0 and t - self._last_move >= c.move_cooldown_s:
            if ry >= rp:
                direction, conf = ("right" if dy > 0 else "left"), ry
            else:
                direction, conf = ("up" if dp > 0 else "down"), rp
            events.append(GestureEvent(event_type="move", target_id=direction, confidence=min(conf / 2, 1.0)))
            self._armed = False
            self._last_move = t

        if frame.blink > c.blink_threshold:
            self._blink_since = self._blink_since if self._blink_since is not None else t
            if t - self._blink_since >= c.blink_hold_s and t - self._last_back >= c.back_cooldown_s:
                events.append(GestureEvent(event_type="back", confidence=min(frame.blink, 1.0)))
                self._last_back = t
                self._blink_since = None
        else:
            self._blink_since = None

        return events
