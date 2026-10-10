"""Visor y editor local del árbol de Melior (solo librería estándar).

Uso:  python3 arbol_viewer/server.py [puerto]     (por defecto 8000)
Variables opcionales: LLM_BASE_URL, LLM_MODEL (por defecto, la VM de Gemma por NetBird).
El árbol se guarda en arbol_viewer/arbol.json y el historial en data/user_history.jsonl.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from src.intelligence.gemma import GemmaClient, day_context  # noqa: E402
from src.intelligence.history import History  # noqa: E402
from src.intelligence.voice import Voice, warm_in_background  # noqa: E402

TREE_PATH = os.path.join(HERE, "arbol.json")
MAX_CHILDREN = 4
GEMMA = GemmaClient()
HISTORY = History()
VOICE = Voice()


def validate(node, trail="Melior"):
    if not isinstance(node, dict) or not isinstance(node.get("label"), str) or not node["label"].strip():
        raise ValueError(f"Nodo sin etiqueta en {trail}")
    children = node.get("children", [])
    if len(children) > MAX_CHILDREN:
        raise ValueError(f"'{node['label']}' tiene {len(children)} opciones (máximo {MAX_CHILDREN})")
    for child in children:
        validate(child, f"{trail} > {node['label']}")


def parse_time(value):
    from datetime import datetime
    if not value:
        return None
    h, m = (int(x) for x in value.split(":")[:2])
    return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, (bytes, str)):
            body = json.dumps(body, ensure_ascii=False)
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/tree":
            with open(TREE_PATH, "rb") as f:
                self._send(200, f.read())
        elif self.path == "/api/history":
            self._send(200, HISTORY.summary())
        elif self.path == "/api/info":
            self._send(200, {"llm": GEMMA.base_url, "model": GEMMA.model, "context": day_context()})
        else:
            self._send(404, "No encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            body = self._json()
            if self.path == "/api/tree":
                validate(body)
                tmp = TREE_PATH + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(body, f, ensure_ascii=False, indent=2)
                os.replace(tmp, TREE_PATH)
                return self._send(200, {"ok": True})
            now = parse_time(body.get("time"))
            if self.path == "/api/suggest":
                path = [str(p) for p in body.get("path", [])]
                use_history = bool(body.get("use_history", True))
                ctx = day_context(now)
                result = GEMMA.suggest(
                    path, str(body.get("prompt", "")), body.get("fallback", []),
                    heard=str(body.get("heard", "")),
                    exclude=[str(e) for e in body.get("exclude", [])],
                    recent=HISTORY.recent() if use_history else [],
                    learned=HISTORY.learned(path, ctx["momento"]) if use_history else [],
                    now=now)
                return self._send(200, result)
            if self.path == "/api/choice":
                HISTORY.record([str(p) for p in body.get("path", [])], str(body["text"]), day_context(now)["momento"], now)
                return self._send(200, {"ok": True})
            if self.path == "/api/speak":
                audio, reason = VOICE.speak(str(body.get("text", "")))
                if audio is None:
                    return self._send(503, {"error": reason})
                return self._send(200, audio, "audio/mpeg")
            if self.path == "/api/history/clear":
                HISTORY.clear()
                return self._send(200, {"ok": True})
            self._send(404, "No encontrado", "text/plain; charset=utf-8")
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    warm_in_background(VOICE)  # frases clásicas del árbol listas en caché
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Melior árbol: http://localhost:{port}  ·  Gemma: {GEMMA.base_url}  (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAdiós")
