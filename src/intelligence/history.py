"""Memoria local de las elecciones del usuario (se guarda en un JSONL, nada sale del equipo).

Es la base del "aprendizaje": cada frase elegida queda registrada y se resume en el contexto
que se le pasa a Gemma. No se reentrena ningún modelo.
"""
import json
import os
from collections import Counter
from datetime import datetime

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "user_history.jsonl")


class History:
    def __init__(self, path=DEFAULT_PATH):
        self.path = os.path.abspath(path)

    def _rows(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []

    def record(self, node_path, text, momento, when=None):
        """node_path: etiquetas del nodo donde se eligió (lista). text: frase dicha."""
        row = {"t": (when or datetime.now()).isoformat(timespec="seconds"),
               "path": " > ".join(node_path), "text": text, "momento": momento}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def learned(self, node_path, momento=None, limit=4):
        """Frases más elegidas en este nodo; pesan más las del mismo momento del día."""
        key = " > ".join(node_path)
        counts, same = Counter(), Counter()
        for r in self._rows():
            if r["path"] == key:
                counts[r["text"]] += 1
                if momento and r.get("momento") == momento:
                    same[r["text"]] += 1
        ranked = sorted(counts, key=lambda t: (same[t], counts[t]), reverse=True)
        return [{"text": t, "veces": counts[t], "en_este_momento": same[t]} for t in ranked[:limit]]

    def recent(self, n=5):
        return [r["text"] for r in self._rows()[-n:]]

    def summary(self, last=15):
        rows = self._rows()
        return {"total": len(rows), "ultimas": rows[-last:][::-1]}

    def clear(self):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
