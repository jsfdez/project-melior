"""Navegador del árbol de Melior: GestureEvent -> pantalla actual. Sin UI, sin cámara.

Recibe los eventos del `GestureEngine` (move / dwell / back), recorre el árbol de
`ArbolConversacion.md` (cargado desde arbol.json) y devuelve con `snapshot()` lo que hay que
dibujar. Es seguro entre hilos: la interfaz lee, Gemma responde en segundo plano.

Convención de direcciones (la misma que el árbol): hijo 0 = up, 1 = down, 2 = left, 3 = right.

Pantallas generadas por Gemma (nodos [IA]): cada llamada trae hasta 6 frases ordenadas; se enseñan
las 3 mejores en up/left/right y `down` es siempre «Más opciones». Al enseñar la última tanda en
cola se lanza en segundo plano otra llamada que excluye todo lo ya generado en esa visita.

Opciones críticas [!]: la primera selección pide confirmación; repetir la misma dirección confirma.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Optional

from src.intelligence.gemma import day_context

DIRS = ["up", "down", "left", "right"]
ARROWS = ["↑", "↓", "←", "→"]
PHRASE_SLOTS = [0, 2, 3]
MORE_SLOT = 1
PAGE = 3
RESET_AFTER_S = 1.8      # tras decir una frase se vuelve al inicio
PENDING_TIMEOUT_S = 6.0  # una confirmación pendiente caduca


def parse_clock(value: str, base: Optional[datetime] = None) -> Optional[datetime]:
    """'HH:MM' -> datetime de hoy a esa hora (para simular el momento del día)."""
    if not value:
        return None
    h, m = (int(x) for x in value.split(":")[:2])
    return (base or datetime.now()).replace(hour=h, minute=m, second=0, microsecond=0)


def has_flag(node: dict, flag: str) -> bool:
    return flag in node.get("flags", [])


class Navigator:
    def __init__(self, tree: dict, gemma=None, history=None,
                 on_speak: Optional[Callable[[str], None]] = None, workers: int = 2):
        self.gemma, self.history, self.on_speak = gemma, history, on_speak
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gemma")
        # Contexto editable desde la UI de pruebas
        self.heard, self.clock, self.use_history = "", "", True
        self.tree = tree
        self._reset_state()
        self._speech_id = 0
        self._speech_text = ""

    # ------------------------------------------------------------------ estado
    def _reset_state(self):
        self.path: list = []
        self.dyn: Optional[dict] = None
        self.pending: Optional[int] = None
        self.pending_since = 0.0
        self.highlight: Optional[int] = None
        self.progress = 0.0
        self.busy = False
        self._token = 0              # invalida respuestas de Gemma de una visita anterior
        self._reset_at: Optional[float] = None
        self.banner = ("Apunta con la cabeza (o usa las flechas) para elegir.", False)

    def set_tree(self, tree: dict):
        """Aplica un árbol editado; mantiene la posición si sigue existiendo."""
        with self.lock:
            self.tree = tree
            try:
                self._node_at(self.path)
            except (IndexError, KeyError):
                self._token += 1
                self.path, self.dyn, self.pending, self.busy = [], None, None, False

    def _node_at(self, path) -> dict:
        n = self.tree
        for i in path:
            n = n["children"][i]
        return n

    def _labels(self, path=None) -> list:
        n, out = self.tree, []
        for i in (self.path if path is None else path):
            n = n["children"][i]
            out.append(n["label"])
        return out

    def _now(self) -> Optional[datetime]:
        try:
            return parse_clock(self.clock)
        except ValueError:
            return None

    def set_context(self, heard=None, clock=None, use_history=None):
        with self.lock:
            if heard is not None:
                self.heard = str(heard)
            if clock is not None:
                self.clock = str(clock)
            if use_history is not None:
                self.use_history = bool(use_history)

    def _say(self, text: str, warn: bool = False):
        self.banner = (text, warn)

    # ------------------------------------------------------------------ entrada
    def set_pointer(self, direction: Optional[str], progress: float = 0.0):
        """Dirección resaltada y progreso del dwell (0..1), tal y como los da el motor de gestos."""
        with self.lock:
            self.highlight = DIRS.index(direction) if direction in DIRS else None
            self.progress = progress if self.highlight is not None else 0.0

    def handle(self, event_type: str, target_id: Optional[str] = None):
        """Procesa un evento del motor de gestos: move | dwell | back (y home, para pruebas)."""
        with self.lock:
            self._tick()
            if event_type == "move":
                self.highlight = DIRS.index(target_id) if target_id in DIRS else None
            elif event_type == "dwell" and target_id in DIRS:
                self.highlight = DIRS.index(target_id)
                self._choose(self.highlight)
            elif event_type == "back":
                self._back()
            elif event_type == "home":
                self._home()

    def goto(self, path: list):
        """Salta a un menú (migas de pan / árbol completo de la UI de pruebas)."""
        with self.lock:
            try:
                self._node_at(path)
            except (IndexError, KeyError):
                return
            self._token += 1
            self.path, self.dyn, self.pending, self.busy = list(path), None, None, False
            self._say(f"Menú «{self._node_at(path)['label']}»")

    # ------------------------------------------------------------------ lógica
    def _tick(self):
        now = time.time()
        if self._reset_at and now >= self._reset_at:
            self._home(quiet=True)
        if self.pending is not None and now - self.pending_since > PENDING_TIMEOUT_S:
            self.pending = None

    def _home(self, quiet=False):
        self._token += 1
        self.path, self.dyn, self.pending, self.busy, self._reset_at = [], None, None, False, None
        if not quiet:
            self._say("Inicio.")

    def _back(self):
        if self.pending is not None:
            self.pending = None
            self._say("Cancelado.")
        elif self.busy:
            self._token += 1
            self.busy = False
            self._say("Cancelado.")
        elif self.dyn:
            self._token += 1
            self.dyn = None
            self._say("Atrás.")
        elif self.path:
            self.path.pop()
            self._say("Atrás.")
        else:
            self._say("Ya estás en el inicio.")

    def _choose(self, i: int):
        if self.busy:
            return
        if self.dyn:
            return self._choose_dyn(i)
        children = self._node_at(self.path).get("children", [])
        if i >= len(children):
            return
        ch = children[i]
        if ch.get("children"):
            self.path.append(i)
            self.pending = None
            self._say(f"Menú «{ch['label']}»")
        elif has_flag(ch, "ia"):
            self.pending = None
            self._start_ia(ch, self._labels() + [ch["label"]])
        elif has_flag(ch, "!") and self.pending != i:
            self.pending, self.pending_since = i, time.time()
            self._say(f"Opción crítica: «{ch.get('say') or ch['label']}». Repite la misma dirección para confirmar, o parpadea largo para cancelar.", True)
        elif has_flag(ch, "aj"):
            self.pending = None
            self._say(f"Ajuste «{ch['label']}» (aún no implementado en las pruebas).")
        else:
            self.pending = None
            self._speak(ch.get("say") or ch["label"], self._labels() + [ch["label"]])

    def _speak(self, text: str, labels: list):
        self._speech_id += 1
        self._speech_text = text
        self._say(f"🔊 {text}")
        self._reset_at = time.time() + RESET_AFTER_S
        if self.history:
            self.history.record(labels, text, day_context(self._now())["momento"], self._now())
        if self.on_speak:
            try:
                self.on_speak(text)
            except Exception as exc:  # la voz nunca debe romper la navegación
                self._say(f"🔊 {text}  (voz: {exc})", True)

    # ------------------------------------------------------------------ Gemma
    def _suggest(self, node: dict, labels: list, exclude: list) -> dict:
        now = self._now()
        ctx = day_context(now)
        with self.lock:
            heard, use = self.heard, self.use_history and self.history is not None
        recent = self.history.recent() if use else []
        learned = self.history.learned(labels, ctx["momento"]) if use else []
        return self.gemma.suggest(labels, node.get("ia_prompt") or node["label"], node.get("fallback", []),
                                  heard=heard, recent=recent, learned=learned, exclude=exclude, now=now)

    @staticmethod
    def _note(r: dict) -> str:
        name = {"llm": "Gemma", "mixed": "Gemma + reserva", "fallback": "Solo reserva", "empty": "Sin opciones"}.get(r["source"], r["source"])
        return f"{name} · {r['ms']} ms · {r['context']['comida']}" + (f" · {r['reason']}" if r.get("reason") else "")

    def _start_ia(self, node: dict, labels: list):
        self.busy = True
        token = self._token
        self._say(f"Preguntando a Gemma para «{node['label']}»…")

        def done(fut):
            with self.lock:
                if token != self._token:
                    return  # el usuario ya se fue de aquí
                self.busy = False
                try:
                    r = fut.result()
                except Exception as exc:
                    r = {"options": [], "source": "empty", "ms": 0, "reason": str(exc), "context": day_context(self._now())}
                self.dyn = {"label": node["label"], "node": node, "labels": labels, "queue": list(r["options"]),
                            "generated": list(r["options"]), "options": [], "page": 0, "no_more": not r["options"],
                            "inflight": None, "waiting": False, "token": token, "source": r["source"]}
                self._show_page()
                self._say(self._note(r), r["source"] in ("fallback", "empty"))

        self.pool.submit(self._suggest, node, labels, []).add_done_callback(done)

    def _show_page(self):
        d = self.dyn
        d["options"] = d["queue"][:PAGE]
        del d["queue"][:PAGE]
        d["page"] += 1
        self._prefetch()

    def _prefetch(self):
        d = self.dyn
        if d["inflight"] or d["no_more"] or len(d["queue"]) >= PAGE:
            return
        fut = self.pool.submit(self._suggest, d["node"], d["labels"], list(d["generated"]))
        d["inflight"] = fut

        def done(f):
            with self.lock:
                if self.dyn is not d:
                    return
                d["inflight"] = None
                try:
                    r = f.result()
                except Exception:
                    r = {"options": [], "source": "empty"}
                if r["options"]:
                    d["queue"].extend(r["options"])
                    d["generated"].extend(r["options"])
                else:
                    d["no_more"] = True
                if d["waiting"]:
                    d["waiting"] = False
                    if d["queue"]:
                        self._show_page()
                        self._say(f"Tanda {d['page']} · {len(d['queue'])} ya preparadas")
                    else:
                        self._say("Ya no quedan opciones nuevas. Parpadea largo para volver.", True)

        fut.add_done_callback(done)

    def _choose_dyn(self, i: int):
        d = self.dyn
        if i == MORE_SLOT:
            if d["queue"]:
                self._show_page()
                self._say(f"Tanda {d['page']} · {len(d['queue'])} ya preparadas" + (" · generando más…" if d["inflight"] else ""))
            elif d["inflight"]:
                d["waiting"] = True
                self._say("Buscando otras opciones…")
            else:
                self._say("Ya no quedan opciones nuevas. Parpadea largo para volver.", True)
            return
        k = PHRASE_SLOTS.index(i) if i in PHRASE_SLOTS else -1
        if 0 <= k < len(d["options"]):
            self._speak(d["options"][k], d["labels"])

    # ------------------------------------------------------------------ salida
    def _slot(self, i: int, ch: Optional[dict]) -> dict:
        base = {"dir": DIRS[i], "arrow": ARROWS[i], "label": None, "tags": [], "sub": "", "kind": "empty", "disabled": True}
        if not ch:
            return base
        tags = [t for t, f in (("IA", "ia"), ("!", "!"), ("AJ", "aj")) if has_flag(ch, f)]
        note = f" · {ch['note']}" if ch.get("note") else ""
        if ch.get("children"):
            kind, sub = "menu", f"{len(ch['children'])} opciones ›"
        elif has_flag(ch, "ia"):
            kind, sub = "ia", "Gemma genera"
        else:
            kind, sub = "leaf", "🔊 se dice"
        return {**base, "label": ch["label"], "tags": tags, "sub": sub + note, "kind": kind, "disabled": False}

    def snapshot(self) -> dict:
        with self.lock:
            self._tick()
            node = self._node_at(self.path)
            ia = None
            if self.dyn:
                d = self.dyn
                done = d["no_more"] and not d["queue"] and not d["inflight"]
                slots = [self._slot(i, None) for i in range(4)]
                for k, i in enumerate(PHRASE_SLOTS):
                    if k < len(d["options"]):
                        slots[i] = {**slots[i], "label": d["options"][k], "kind": "phrase", "sub": "🔊 se dice", "disabled": False}
                slots[MORE_SLOT] = {**slots[MORE_SLOT], "label": "Sin más opciones" if done else "Más opciones",
                                    "kind": "more", "sub": "" if done else "🔄 nuevas, sin repetir", "disabled": done}
                title = d["label"]
                ia = {"source": d["source"], "page": d["page"], "queued": len(d["queue"]), "loading": bool(d["inflight"])}
            else:
                kids = node.get("children", [])
                slots = [self._slot(i, kids[i] if i < len(kids) else None) for i in range(4)]
                title = node["label"]
            return {
                "title": title, "crumbs": self._labels() + ([self.dyn["label"]] if self.dyn else []), "path": list(self.path),
                "slots": slots, "highlight": self.highlight, "progress": round(self.progress, 3), "pending": self.pending,
                "banner": {"text": self.banner[0], "warn": self.banner[1]}, "busy": self.busy, "ia": ia,
                "speech": {"id": self._speech_id, "text": self._speech_text},
                "context": {"heard": self.heard, "clock": self.clock, "use_history": self.use_history},
            }
