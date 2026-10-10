"""Entrada en vivo: cámara -> VisionWorker -> GestureEngine -> Navigator.

Pensado para el localhost de pruebas (y reutilizable por la app de escritorio). Mantiene el último
frame de la cámara, con un pequeño resumen encima, listo para servirlo como vista previa.

Importa visión (OpenCV / MediaPipe) solo al arrancar: sin esas librerías el resto sigue funcionando
y `status` explica qué falta.
"""
import queue
import threading
import time
from typing import Optional

from src.core.contracts import VisionFrame
from src.interaction.gesture_engine import GestureEngine


def has_face(vf: VisionFrame) -> bool:
    """`VisionWorker` rellena con una pose a cero los frames sin cara; eso no es una pose real."""
    p = vf.head_pose
    return not (p.yaw == 0.0 and p.pitch == 0.0 and p.roll == 0.0 and vf.blink == 0.0)


NO_FRAMES_S = 8.0  # sin imágenes tras este tiempo: casi seguro falta el permiso de cámara


class LiveInput:
    def __init__(self, navigator, engine: Optional[GestureEngine] = None):
        self.nav = navigator
        self.engine = engine or GestureEngine()
        self.queue: queue.Queue = queue.Queue(maxsize=10)
        self._worker = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started = time.time()
        self._lock = threading.Lock()
        self._jpeg: Optional[bytes] = None
        self._status = {"state": "stopped", "error": None, "calibrated": False, "face": False, "fps": 0.0}

    # -------------------------------------------------------------- ciclo de vida
    def start(self) -> bool:
        try:
            from src.core.vision_worker import VisionWorker  # importa cv2 y mediapipe
            import cv2  # noqa: F401
        except Exception as exc:  # falta alguna librería
            self._set(state="unavailable", error=f"{type(exc).__name__}: {exc}")
            return False
        self._worker = VisionWorker(output_queue=self.queue)
        self._worker.start()
        self._thread = threading.Thread(target=self._loop, name="live-input", daemon=True)
        self._thread.start()
        self._started = time.time()
        self._set(state="starting", error=None)
        return True

    def stop(self):
        self._stop.set()
        if self._worker:
            self._worker.stop()
            self._worker.join(timeout=3)
        self._set(state="stopped")

    def recalibrate(self):
        self.engine.recalibrate()
        self._set(calibrated=False)

    # -------------------------------------------------------------- estado
    def _set(self, **kw):
        with self._lock:
            self._status.update(kw)

    @property
    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._jpeg

    # -------------------------------------------------------------- bucle
    def _loop(self):
        import cv2
        frames, t0 = 0, time.time()
        while not self._stop.is_set():
            try:
                vf = self.queue.get(timeout=0.3)
            except queue.Empty:
                if self._worker and not self._worker.is_alive():
                    self._set(state="error", error="la cámara o el seguimiento se detuvieron (¿permiso de cámara?)")
                    return
                if self.status["state"] == "starting" and time.time() - self._started > NO_FRAMES_S:
                    self._set(state="error", error="no llegan imágenes de la cámara: revisa el permiso de cámara de la "
                                                   "aplicación desde la que lanzas el servidor (Terminal, VS Code...)")
                continue
            face = has_face(vf)
            events = self.engine.update(vf if face else None)
            for e in events:
                self.nav.handle(e.event_type, e.target_id)
            self.nav.set_pointer(self.engine.current if face else None, self.engine.dwell_progress)
            frames += 1
            if time.time() - t0 >= 1.0:
                self._set(fps=round(frames / (time.time() - t0), 1))
                frames, t0 = 0, time.time()
            self._set(state="running", calibrated=self.engine.calibrated, face=face)
            ok, buf = cv2.imencode(".jpg", self._overlay(cv2, vf, face), [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._lock:
                    self._jpeg = buf.tobytes()

    def _overlay(self, cv2, vf: VisionFrame, face: bool):
        img = cv2.flip(vf.frame, 1)  # vista de espejo: más natural al mirarse
        h, w = img.shape[:2]
        if not face:
            msg, color = "No veo tu cara", (60, 60, 230)
        elif not self.engine.calibrated:
            msg, color = "Calibrando: mira al frente y quieto", (40, 180, 240)
        else:
            dy, dp = self.engine.deviation()
            msg, color = f"yaw {dy:+.0f}  pitch {dp:+.0f}  blink {vf.blink:.2f}", (90, 200, 90)
        cv2.rectangle(img, (0, 0), (w, 28), (20, 20, 20), -1)
        cv2.putText(img, msg, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
        if self.engine.current and face:
            bar = int(w * self.engine.dwell_progress)
            cv2.rectangle(img, (0, h - 8), (bar, h), (255, 170, 60), -1)
        return img
