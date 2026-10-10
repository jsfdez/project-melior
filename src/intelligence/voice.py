"""Voz de Melior con ElevenLabs (solo librería estándar).

Una única voz genérica (ELEVENLABS_VOICE_ID) para todo, también para las frases críticas: no hay voz
local de reserva. La reserva es la caché en disco: `python -m src.intelligence.voice warm` genera de
antemano el audio de todas las frases del árbol, así suenan aunque no haya red. Nunca lanza excepciones.

Uso:  python -m src.intelligence.voice warm     (precalienta la caché con las frases de arbol.json)
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(ROOT, "data", "tts_cache")
TREE_PATH = os.path.join(ROOT, "arbol_viewer", "arbol.json")
API = "https://api.elevenlabs.io/v1/text-to-speech"
MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
TIMEOUT_S = 5.0
BREAKER_FAILS = 3
BREAKER_PAUSE_S = 60


def load_env(path=os.path.join(ROOT, ".env")):
    """Carga .env sin dependencias; no pisa variables ya definidas."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and not k.startswith("#"):
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


class Voice:
    def __init__(self, api_key=None, voice_id=None, cache_dir=CACHE_DIR):
        load_env()
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", "")
        self.cache_dir = cache_dir
        self.fails = 0
        self.paused_until = 0.0

    def _path(self, text):
        key = hashlib.sha1(f"{self.voice_id}|{MODEL}|{text}".encode()).hexdigest()
        return os.path.join(self.cache_dir, key + ".mp3")

    def _synthesize(self, text):
        body = {"text": text, "model_id": MODEL}
        req = urllib.request.Request(
            f"{API}/{self.voice_id}?output_format={OUTPUT_FORMAT}", json.dumps(body).encode(),
            {"Content-Type": "application/json", "xi-api-key": self.api_key, "Accept": "audio/mpeg"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.read()

    def speak(self, text):
        """Devuelve (mp3 | None, motivo | None). Primero la caché; si no, ElevenLabs."""
        text = text.strip()
        if not text:
            return None, "texto vacío"
        path = self._path(text)
        try:
            with open(path, "rb") as f:
                return f.read(), None
        except OSError:
            pass
        if not (self.api_key and self.voice_id):
            return None, "faltan ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID"
        if time.time() < self.paused_until:
            return None, "pausado tras varios fallos seguidos (circuit breaker)"
        try:
            audio = self._synthesize(text)
            self.fails = 0
        except Exception as exc:  # red, timeout, HTTP: la interfaz sigue mostrando el texto
            self.fails += 1
            if self.fails >= BREAKER_FAILS:
                self.paused_until = time.time() + BREAKER_PAUSE_S
            return None, f"{type(exc).__name__}: {exc}"
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(audio)
            os.replace(tmp, path)
        except OSError:
            pass
        return audio, None


def tree_phrases(node, out=None):
    """Frases que se pueden decir: hojas (say o label) y opciones de reserva de los nodos [IA]."""
    out = [] if out is None else out
    children = node.get("children", [])
    if not children:
        out.append(node.get("say") or node["label"])
    out.extend(node.get("fallback", []))
    for c in children:
        tree_phrases(c, out)
    return out


def warm(voice=None, quiet=False):
    """Genera el audio de todas las frases del árbol que aún no estén en caché."""
    with open(TREE_PATH, encoding="utf-8") as f:
        phrases = list(dict.fromkeys(p.strip() for p in tree_phrases(json.load(f)) if p.strip()))
    voice, bad = voice or Voice(), 0
    for i, p in enumerate(phrases, 1):
        audio, reason = voice.speak(p)
        bad += audio is None
        if not quiet:
            print(f"[{i}/{len(phrases)}] {'ok ' if audio else 'ERR'} {p}" + (f"  ({reason})" if reason else ""))
        if audio is None and voice.paused_until > time.time():
            break
    print(f"Voz: {len(phrases) - bad}/{len(phrases)} frases en caché.")


def warm_in_background(voice):
    import threading
    threading.Thread(target=warm, args=(voice, True), daemon=True).start()


if __name__ == "__main__":
    if sys.argv[1:] == ["warm"]:
        warm()
    else:
        print(__doc__)
