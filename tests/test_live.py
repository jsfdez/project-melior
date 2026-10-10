"""Cadena visión -> gestos -> navegador con frames sintéticos (sin cámara)."""
import time

import numpy as np
import pytest

from src.core.contracts import HeadPose, VisionFrame
from src.interaction.live import LiveInput, has_face
from src.interaction.navigator import Navigator

TREE = {"label": "Melior", "children": [
    {"label": "Responder", "children": [{"label": "Sí"}, {"label": "No"}]},
    {"label": "Necesito"}, {"label": "Urgencia"}, {"label": "Más"}]}
BLANK = np.zeros((48, 64, 3), dtype=np.uint8)


def frame(t, yaw=1.0, pitch=1.0, blink=0.0):
    return VisionFrame(timestamp=t, head_pose=HeadPose(pitch=pitch, yaw=yaw, roll=0.0), blink=blink, frame=BLANK)


def run_frames(live, frames):
    """Mete los frames en la cola y espera a que el hilo los consuma."""
    for f in frames:
        live.queue.put(f, timeout=1)
    end = time.time() + 5
    while not live.queue.empty() and time.time() < end:
        time.sleep(0.01)
    time.sleep(0.1)


@pytest.fixture
def live():
    nav = Navigator(TREE, gemma=None, history=None)
    li = LiveInput(nav)
    li._started = time.time()
    import threading
    li._thread = threading.Thread(target=li._loop, daemon=True)
    li._thread.start()
    yield li
    li._stop.set()
    li._thread.join(timeout=2)


def calibrate(live, t0=0.0):
    run_frames(live, [frame(t0 + k * 0.1) for k in range(20)])  # 2 s mirando al frente
    return t0 + 2.0


def test_calibrates_from_first_frames(live):
    assert not live.engine.calibrated
    calibrate(live)
    assert live.engine.calibrated and live.status["calibrated"]


def test_head_pointing_moves_and_selects_in_the_tree(live):
    t = calibrate(live)
    # yaw_sign = -1: girar la cabeza en negativo es "derecha"; el hijo 3 (right) de la raíz es «Más»
    frames = [frame(t + k * 0.05, yaw=1.0 - 12.0) for k in range(40)]  # 2 s apuntando y quieto
    run_frames(live, frames)
    assert live.nav.snapshot()["speech"]["text"] == "Más"


def test_pointing_down_selects_the_second_option(live):
    t = calibrate(live)
    run_frames(live, [frame(t + k * 0.05, pitch=1.0 + 12.0) for k in range(50)])
    # pitch_sign = -1: pitch positivo = abajo = hijo 1 = «Necesito» (hoja: se dice)
    assert live.nav.snapshot()["speech"]["text"] == "Necesito"


def test_long_blink_goes_back(live):
    t = calibrate(live)
    live.nav.goto([0])
    assert live.nav.snapshot()["title"] == "Responder"
    run_frames(live, [frame(t + k * 0.05, blink=0.9) for k in range(20)])  # 1 s con los ojos cerrados
    assert live.nav.snapshot()["title"] == "Melior"


def test_short_natural_blink_is_ignored(live):
    t = calibrate(live)
    live.nav.goto([0])
    run_frames(live, [frame(t + k * 0.05, blink=0.9) for k in range(4)] + [frame(t + 0.3 + k * 0.05) for k in range(5)])
    assert live.nav.snapshot()["title"] == "Responder"


def test_frames_without_face_are_not_treated_as_a_pose():
    assert not has_face(frame(0.0, yaw=0.0, pitch=0.0))
    assert has_face(frame(0.0, yaw=0.3, pitch=0.0))


def test_no_face_frames_do_not_calibrate_or_trigger(live):
    run_frames(live, [frame(k * 0.1, yaw=0.0, pitch=0.0) for k in range(30)])
    assert not live.engine.calibrated and live.nav.snapshot()["speech"]["id"] == 0
