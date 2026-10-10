"""Gesture engine: VisionFrame -> GestureEvent. No UI, no LLM, no TTS.

Interaction model ("point and hold"):
  1. Move the head slightly away from neutral towards an option.
  2. Once that direction is stable for `stable_s`, the engine emits "move" (highlight it).
  3. Keep the head still for `dwell_s` and it emits "dwell" (that option is selected).
  4. Return to neutral to re-arm. Moving to another direction before the dwell restarts the timer.
  5. A long blink emits "back".

Events (GestureEvent.event_type / target_id):
  "move"   left | right | up | down   highlighted direction changed
  "dwell"  left | right | up | down   held still long enough: selected
  "back"   -                          long blink: go back / cancel

Neutral pose is learned from the first frames; call `recalibrate()` to redo it.
"""
import math
from dataclasses import dataclass
from typing import List, Optional

from src.core.contracts import GestureEvent, VisionFrame


class OneEuro:
    """Adaptive low-pass: smooth when still, almost no lag when moving fast."""

    def __init__(self, min_cutoff: float = 1.5, beta: float = 0.08, d_cutoff: float = 1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        if self.x is None:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = max(t - self.t, 1e-3)
        dx = (x - self.x) / dt
        self.dx += self._alpha(self.d_cutoff, dt) * (dx - self.dx)
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        self.x += self._alpha(cutoff, dt) * (x - self.x)
        self.t = t
        return self.x


@dataclass
class GestureConfig:
    yaw_deg: float = 7.0           # turn from neutral that counts as "left/right"
    pitch_deg: float = 6.0         # tilt from neutral that counts as "up/down"
    exit_ratio: float = 0.6        # below this fraction of the threshold = back at center
    axis_margin: float = 1.4       # one axis must beat the other by this factor (avoids diagonals)
    stable_s: float = 0.2          # direction must hold this long before "move" (filters jitter)
    dwell_s: float = 1.0           # stillness needed to select
    still_deg: float = 3.0         # head may drift this much and still count as "still"
    blink_threshold: float = 0.5   # eyeBlink score (0..1)
    blink_hold_s: float = 0.6      # a natural blink is ~0.1-0.4 s
    back_cooldown_s: float = 1.5
    neutral_seconds: float = 1.5
    # One Euro filter: lower min_cutoff = smoother at rest; higher beta = less lag when moving
    min_cutoff: float = 1.5
    beta: float = 0.08
    # Flip if directions come out inverted on your camera
    yaw_sign: int = -1
    pitch_sign: int = -1


class GestureEngine:
    def __init__(self, config: Optional[GestureConfig] = None):
        self.cfg = config or GestureConfig()
        self.recalibrate()

    def recalibrate(self):
        self._samples: List[tuple] = []
        self._t_start: Optional[float] = None
        self.neutral: Optional[tuple] = None  # raw (yaw, pitch)
        self._yaw = self._pitch = None
        self._fy = OneEuro(self.cfg.min_cutoff, self.cfg.beta)
        self._fp = OneEuro(self.cfg.min_cutoff, self.cfg.beta)
        self._candidate: Optional[str] = None
        self._candidate_since = 0.0
        self.current: Optional[str] = None     # highlighted direction
        self._anchor: Optional[tuple] = None   # (dy, dp) where stillness started
        self._still_since = 0.0
        self._selected = False                 # dwell already fired; wait for return to center
        self._blink_since: Optional[float] = None
        self._last_back = -1e9

    @property
    def calibrated(self) -> bool:
        return self.neutral is not None

    @property
    def dwell_progress(self) -> float:
        """0..1 progress towards selecting the current direction (for UI)."""
        return self._progress

    _progress = 0.0

    def deviation(self) -> tuple:
        """Smoothed (yaw, pitch) relative to neutral, sign-corrected, for overlays/debug."""
        if self.neutral is None or self._yaw is None:
            return 0.0, 0.0
        return (self._yaw - self.neutral[0]) * self.cfg.yaw_sign, (self._pitch - self.neutral[1]) * self.cfg.pitch_sign

    def _direction(self, dy: float, dp: float, entering: bool) -> Optional[str]:
        c = self.cfg
        k = 1.0 if entering else c.exit_ratio
        ry, rp = abs(dy) / (c.yaw_deg * k), abs(dp) / (c.pitch_deg * k)
        if max(ry, rp) < 1.0:
            return None
        # Turning sideways leaks into pitch (and vice versa): require a clear winner
        if ry >= rp * c.axis_margin:
            return "right" if dy > 0 else "left"
        if rp >= ry * c.axis_margin:
            return "up" if dp > 0 else "down"
        return self.current or self._candidate  # ambiguous diagonal: keep what we had (or nothing)

    def update(self, frame: Optional[VisionFrame]) -> List[GestureEvent]:
        c = self.cfg
        if frame is None:  # face lost: drop transient state
            self._reset_pointing()
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

        self._yaw = self._fy(yaw, t)
        self._pitch = self._fp(pitch, t)

        events: List[GestureEvent] = []
        dy, dp = self.deviation()
        # Hysteresis: easier to stay in a direction than to enter one
        direction = self._direction(dy, dp, entering=self.current is None and self._candidate is None)
        if direction is None:
            self._reset_pointing()
        else:
            events += self._point(direction, dy, dp, t)

        events += self._blink(frame, t)
        return events

    def _reset_pointing(self):
        self._candidate = None
        self.current = None
        self._anchor = None
        self._selected = False
        self._progress = 0.0

    def _point(self, direction: str, dy: float, dp: float, t: float) -> List[GestureEvent]:
        c = self.cfg
        events: List[GestureEvent] = []
        if self._selected:  # already selected: wait until the head returns to center
            return events

        if direction != self.current:
            if direction != self._candidate:
                self._candidate, self._candidate_since = direction, t
                self._progress = 0.0
            if t - self._candidate_since >= c.stable_s:
                self.current = direction
                self._anchor, self._still_since = (dy, dp), t
                events.append(GestureEvent(event_type="move", target_id=direction, confidence=1.0))
            return events

        # Same highlighted direction: count stillness
        if math.hypot(dy - self._anchor[0], dp - self._anchor[1]) > c.still_deg:
            self._anchor, self._still_since = (dy, dp), t
            self._progress = 0.0
            return events
        self._progress = min((t - self._still_since) / c.dwell_s, 1.0)
        if self._progress >= 1.0:
            events.append(GestureEvent(event_type="dwell", target_id=direction, confidence=1.0))
            self._selected = True
        return events

    def _blink(self, frame: VisionFrame, t: float) -> List[GestureEvent]:
        c = self.cfg
        if frame.blink <= c.blink_threshold:
            self._blink_since = None
            return []
        self._blink_since = self._blink_since if self._blink_since is not None else t
        if t - self._blink_since >= c.blink_hold_s and t - self._last_back >= c.back_cooldown_s:
            self._last_back = t
            self._blink_since = None
            return [GestureEvent(event_type="back", confidence=min(frame.blink, 1.0))]
        return []
