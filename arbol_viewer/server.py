"""Localhost de pruebas de Melior: todo integrado (solo librería estándar + las libs de visión).

Cámara -> MediaPipe -> GestureEngine -> Navigator (árbol) -> Gemma / historial -> ElevenLabs.
La página (index.html) dibuja el estado del Navigator y deja editar el árbol.

Uso:   ./venv/bin/python arbol_viewer/server.py [puerto] [--no-camera]
Variables: LLM_BASE_URL, LLM_MODEL (Gemma, por defecto la VM por NetBird),
           ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (en .env o en el entorno).
El árbol se guarda en arbol_viewer/arbol.json y el historial en data/user_history.jsonl.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from src.interaction.live import LiveInput  # noqa: E402
from src.interaction.navigator import Navigator, parse_clock  # noqa: E402
from src.intelligence.gemma import GemmaClient, day_context  # noqa: E402
from src.intelligence.history import History  # noqa: E402
from src.intelligence.voice import Voice, load_env  # noqa: E402

TREE_PATH = os.path.join(HERE, "arbol.json")
MAX_CHILDREN = 4

load_env()  # .env antes de crear los clientes (Gemma lee LLM_BASE_URL del entorno)
GEMMA = GemmaClient()
HISTORY = History()
VOICE = Voice()


def load_tree():
    with open(TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


NAV = Navigator(load_tree(), GEMMA, HISTORY)
LIVE = LiveInput(NAV)


def validate(node, trail="Melior"):
    if not isinstance(node, dict) or not isinstance(node.get("label"), str) or not node["label"].strip():
        raise ValueError(f"Nodo sin etiqueta en {trail}")
    children = node.get("children", [])
    if len(children) > MAX_CHILDREN:
        raise ValueError(f"'{node['label']}' tiene {len(children)} opciones (máximo {MAX_CHILDREN})")
    for child in children:
        validate(child, f"{trail} > {node['label']}")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body, ensure_ascii=False)
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html", "/admin", "/admin/"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif url.path == "/api/tree":
            self._send(200, load_tree())
        elif url.path == "/api/state":
            self._send(200, {**NAV.snapshot(), "live": LIVE.status,
                             "voice": {"configured": bool(VOICE.api_key and VOICE.voice_id)}})
        elif url.path == "/api/history":
            self._send(200, HISTORY.summary())
        elif url.path == "/api/info":
            self._send(200, {"llm": GEMMA.base_url, "model": GEMMA.model, "context": day_context()})
        elif url.path == "/api/audio":
            text = urllib.parse.parse_qs(url.query).get("text", [""])[0]
            audio, reason = VOICE.speak(text)
            if audio:
                self._send(200, audio, "audio/mpeg")
            else:
                self._send(204, b"", "text/plain", {"X-Voice-Reason": urllib.parse.quote(reason or "")})
        elif url.path == "/api/camera.mjpg":
            self._stream_camera()
        else:
            self._send(404, "No encontrado", "text/plain; charset=utf-8")

    def _stream_camera(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last = None
        try:
            while True:
                jpg = LIVE.jpeg()
                if jpg and jpg is not last:
                    last = jpg
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                    self.wfile.write(jpg + b"\r\n")
                time.sleep(0.04)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ------------------------------------------------------------------ POST
    def do_POST(self):
        try:
            body = self._json()
            if self.path == "/api/tree":
                validate(body)
                tmp = TREE_PATH + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(body, f, ensure_ascii=False, indent=2)
                os.replace(tmp, TREE_PATH)
                NAV.set_tree(body)
                return self._send(200, {"ok": True})
            if self.path == "/api/gesture":  # mismo camino que la cámara: pruebas con teclado o clic
                NAV.handle(str(body.get("event_type", "")), body.get("target_id"))
                return self._send(200, {"ok": True})
            if self.path == "/api/goto":
                NAV.goto([int(i) for i in body.get("path", [])])
                return self._send(200, {"ok": True})
            if self.path == "/api/context":
                NAV.set_context(body.get("heard"), body.get("clock"), body.get("use_history"))
                return self._send(200, {"ok": True})
            if self.path == "/api/recalibrate":
                LIVE.recalibrate()
                return self._send(200, {"ok": True})
            if self.path == "/api/suggest":  # prueba directa de un prompt (también el sin guardar)
                path = [str(p) for p in body.get("path", [])]
                use_history = bool(body.get("use_history", True))
                now = parse_clock(body.get("time"))
                ctx = day_context(now)
                result = GEMMA.suggest(
                    path, str(body.get("prompt", "")), body.get("fallback", []),
                    heard=str(body.get("heard", "")),
                    exclude=[str(e) for e in body.get("exclude", [])],
                    recent=HISTORY.recent() if use_history else [],
                    learned=HISTORY.learned(path, ctx["momento"]) if use_history else [],
                    now=now)
                return self._send(200, result)
            if self.path == "/api/history/clear":
                HISTORY.clear()
                return self._send(200, {"ok": True})
            self._send(404, "No encontrado", "text/plain; charset=utf-8")
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("port", nargs="?", type=int, default=8000)
    ap.add_argument("--no-camera", action="store_true", help="solo teclado/clic, sin cámara")
    args = ap.parse_args()
    if not args.no_camera and not LIVE.start():
        print(f"⚠️  Sin cámara: {LIVE.status['error']}\n    (usa ./venv/bin/python para tener visión; sigue funcionando con teclado)")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    voice = "configurada" if VOICE.api_key and VOICE.voice_id else "SIN configurar (.env)"
    print(f"Melior localhost: http://localhost:{args.port}\n  Gemma: {GEMMA.base_url}\n  ElevenLabs: {voice}\n  Cámara: {LIVE.status['state']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAdiós")
    finally:
        LIVE.stop()


if __name__ == "__main__":
    main()
