import time

import pytest

from src.interaction.navigator import Navigator


class FakeGemma:
    """Devuelve lotes de 6 frases numeradas y recuerda lo que se le pidió excluir."""

    def __init__(self, batches=3, fail=False):
        self.calls, self.batches, self.fail = [], batches, fail

    def suggest(self, path, prompt, fallback, heard="", recent=(), learned=(), exclude=(), now=None):
        self.calls.append({"path": path, "exclude": list(exclude), "heard": heard})
        if self.fail:
            raise RuntimeError("sin red")
        n = len(self.calls)
        options = [f"frase {n}.{k}" for k in range(1, 7)] if n <= self.batches else []
        return {"options": options, "source": "llm" if options else "empty", "ms": 5, "reason": None,
                "context": {"momento": "mañana", "comida": "desayuno", "saludo": "buenos días", "hora": "08:00"}}


class FakeHistory:
    def __init__(self):
        self.rows = []

    def record(self, path, text, momento, when=None):
        self.rows.append((path, text, momento))

    def recent(self, n=5):
        return [r[1] for r in self.rows[-n:]]

    def learned(self, path, momento=None, limit=4):
        return []


TREE = {"label": "Melior", "children": [
    {"label": "Responder", "children": [{"label": "Sí"}, {"label": "No"}]},
    {"label": "Necesito", "children": [
        {"label": "Tengo hambre", "flags": ["ia"], "ia_prompt": "comidas", "fallback": ["a", "b"]}]},
    {"label": "Urgencia", "children": [{"label": "No puedo respirar", "flags": ["!"]}]},
    {"label": "Más", "children": [{"label": "Hola"}]},
]}


def make(gemma=None):
    spoken, hist = [], FakeHistory()
    nav = Navigator(TREE, gemma or FakeGemma(), hist, on_speak=spoken.append)
    return nav, spoken, hist


def wait(nav, cond, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond(nav.snapshot()):
            return nav.snapshot()
        time.sleep(0.01)
    raise AssertionError(f"condición no cumplida: {nav.snapshot()['banner']}")


def labels(snap):
    return [s["label"] for s in snap["slots"]]


def test_root_slots_follow_up_down_left_right_order():
    nav, _, _ = make()
    assert labels(nav.snapshot()) == ["Responder", "Necesito", "Urgencia", "Más"]
    assert [s["dir"] for s in nav.snapshot()["slots"]] == ["up", "down", "left", "right"]


def test_dwell_enters_menu_and_back_returns():
    nav, _, _ = make()
    nav.handle("dwell", "up")
    assert nav.snapshot()["title"] == "Responder" and labels(nav.snapshot())[:2] == ["Sí", "No"]
    nav.handle("back")
    assert nav.snapshot()["title"] == "Melior"


def test_leaf_is_spoken_recorded_and_returns_home():
    nav, spoken, hist = make()
    nav.handle("dwell", "up")
    nav.handle("dwell", "up")
    assert spoken == ["Sí"] and hist.rows[0][:2] == (["Responder", "Sí"], "Sí")
    assert nav.snapshot()["speech"] == {"id": 1, "text": "Sí"}
    nav._reset_at = time.time() - 1
    assert nav.snapshot()["title"] == "Melior"


def test_critical_option_needs_the_same_direction_twice():
    nav, spoken, _ = make()
    nav.handle("dwell", "left")
    nav.handle("dwell", "up")
    assert spoken == [] and nav.snapshot()["pending"] == 0 and nav.snapshot()["banner"]["warn"]
    nav.handle("dwell", "up")
    assert spoken == ["No puedo respirar"]


def test_back_cancels_a_pending_critical_option():
    nav, spoken, _ = make()
    nav.handle("dwell", "left")
    nav.handle("dwell", "up")
    nav.handle("back")
    assert nav.snapshot()["pending"] is None and spoken == []


def test_ia_node_shows_best_three_and_more_slot_down():
    g = FakeGemma()
    nav, spoken, _ = make(g)
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    snap = wait(nav, lambda s: s["ia"] is not None)
    assert labels(snap) == ["frase 1.1", "Más opciones", "frase 1.2", "frase 1.3"]
    assert g.calls[0]["path"] == ["Necesito", "Tengo hambre"]
    nav.handle("dwell", "left")
    assert spoken == ["frase 1.2"]


def test_more_options_shows_queue_then_prefetches_without_repeats():
    g = FakeGemma()
    nav, _, _ = make(g)
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    wait(nav, lambda s: s["ia"])
    nav.handle("dwell", "down")  # Más opciones: las otras 3 de la cola, al instante
    snap = nav.snapshot()
    assert labels(snap) == ["frase 1.4", "Más opciones", "frase 1.5", "frase 1.6"]
    wait(nav, lambda s: s["ia"]["queued"] >= 3)  # llegó la llamada 2 en segundo plano
    assert g.calls[1]["exclude"] == [f"frase 1.{k}" for k in range(1, 7)]
    nav.handle("dwell", "down")
    assert labels(nav.snapshot()) == ["frase 2.1", "Más opciones", "frase 2.2", "frase 2.3"]


def test_more_waits_for_inflight_call_when_queue_is_empty():
    g = FakeGemma()
    nav, _, _ = make(g)
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    wait(nav, lambda s: s["ia"])
    nav.handle("dwell", "down")
    nav.handle("dwell", "down")  # puede que la llamada 2 aún no haya vuelto
    snap = wait(nav, lambda s: labels(s)[0] == "frase 2.1")
    assert snap["ia"]["page"] == 3


def test_options_run_out_and_slot_is_disabled():
    g = FakeGemma(batches=1)
    nav, _, _ = make(g)
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    wait(nav, lambda s: s["ia"])
    nav.handle("dwell", "down")
    wait(nav, lambda s: not s["ia"]["loading"])
    snap = nav.snapshot()
    assert snap["slots"][1]["label"] == "Sin más opciones" and snap["slots"][1]["disabled"]


def test_gemma_failure_gives_empty_screen_not_a_crash():
    nav, _, _ = make(FakeGemma(fail=True))
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    snap = wait(nav, lambda s: s["ia"] is not None)
    assert snap["slots"][1]["disabled"] and snap["banner"]["warn"]


def test_back_while_waiting_for_gemma_ignores_late_answer():
    slow = FakeGemma()
    original = slow.suggest

    def slow_suggest(*a, **k):
        time.sleep(0.2)
        return original(*a, **k)

    slow.suggest = slow_suggest
    nav, _, _ = make(slow)
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    assert nav.snapshot()["busy"]
    nav.handle("back")
    time.sleep(0.4)
    snap = nav.snapshot()
    assert snap["ia"] is None and not snap["busy"] and snap["title"] == "Necesito"


def test_context_reaches_gemma():
    g = FakeGemma()
    nav, _, _ = make(g)
    nav.set_context(heard="¿Quieres comer algo?")
    nav.handle("dwell", "down")
    nav.handle("dwell", "up")
    wait(nav, lambda s: s["ia"])
    assert g.calls[0]["heard"] == "¿Quieres comer algo?"


def test_set_tree_keeps_position_when_still_valid_and_resets_otherwise():
    nav, _, _ = make()
    nav.handle("dwell", "up")
    nav.set_tree(TREE)
    assert nav.snapshot()["title"] == "Responder"
    nav.set_tree({"label": "Melior", "children": []})
    assert nav.snapshot()["title"] == "Melior"


def test_pointer_is_exposed_for_the_ui():
    nav, _, _ = make()
    nav.set_pointer("left", 0.4)
    snap = nav.snapshot()
    assert snap["highlight"] == 2 and snap["progress"] == 0.4
    nav.set_pointer(None)
    assert nav.snapshot()["highlight"] is None
