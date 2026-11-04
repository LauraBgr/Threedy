"""Sichtbarkeit in KI-Antworten (AISEO): Welche Anbieter nennt ein Sprachmodell auf typische Käuferfragen?

Hinweis: Das Modell antwortet aus seinem Trainingswissen, nicht aus einer Live-Suche. Das Ergebnis ist ein
Näherungswert dafür, wie präsent eine Marke im 'Gedächtnis' von KI-Assistenten ist, und wird über die Zeit verfolgt.
"""
import datetime as dt
import hashlib
import re

from . import ki
from .pfade import DATEN, lies_json, schreib_json

VERLAUF = DATEN / "ki_sichtbarkeit_verlauf.json"
SYSTEM = ("Answer the question as a helpful, neutral assistant would for a buyer. Name concrete vendors and products, "
          "at most 8, as a short list with one sentence each. Do not ask follow-up questions.\n\nQuestion: ")


def _treffer(text, aliase):
    """Position der ersten Erwähnung (oder None)."""
    pos = [m.start() for a in aliase for m in re.finditer(r"(?<![a-z0-9])" + re.escape(a.lower()) + r"(?![a-z0-9])", text.lower())]
    return min(pos) if pos else None


def pruefen(cfg, cache, mit_ki, protokoll=print):
    fragen = ((cfg.get("ki_sichtbarkeit") or {}).get("fragen")) or []
    if not mit_ki or not fragen:
        return {"aktiv": False, "fragen": [], "firmen": [], "verlauf": lies_json(VERLAUF, [])}
    heute = dt.date.today().isoformat()
    aliase = {w["name"]: [w["name"]] + list(w.get("aliase") or []) for w in cfg["wettbewerber"]}
    ergebnisse = []
    for frage in fragen:
        k = "sicht|" + hashlib.sha256((frage + ki.konfiguration()["modell"] + heute).encode()).hexdigest()[:16]
        antwort = cache.get(k)
        if antwort is None:
            try:
                antwort = ki.fragen(SYSTEM + frage, json_antwort=False)
                cache[k] = antwort
            except Exception as ex:
                protokoll(f"   KI ! Sichtbarkeit: {ex}")
                continue
        genannt = sorted(((pos, name) for name, al in aliase.items() if (pos := _treffer(antwort, al)) is not None))
        ergebnisse.append({"frage": frage, "antwort": antwort[:2500], "genannt": [n for _, n in genannt]})
    protokoll(f"   KI ✓ Sichtbarkeit in KI-Antworten ({len(ergebnisse)} Fragen)")
    n = max(1, len(ergebnisse))
    firmen = []
    for name in aliase:
        plaetze = [e["genannt"].index(name) + 1 for e in ergebnisse if name in e["genannt"]]
        firmen.append({"firma": name, "anteil": round(len(plaetze) / n, 2), "nennungen": len(plaetze),
                       "mittlerer_platz": round(sum(plaetze) / len(plaetze), 1) if plaetze else None})
    firmen.sort(key=lambda f: (-f["anteil"], f["mittlerer_platz"] or 99))
    verlauf = [v for v in lies_json(VERLAUF, []) if v["datum"] != heute] + [{"datum": heute, "anteile": {f["firma"]: f["anteil"] for f in firmen}}]
    schreib_json(VERLAUF, verlauf[-52:])
    return {"aktiv": True, "modell": ki.konfiguration()["modell"], "fragen": ergebnisse, "firmen": firmen, "verlauf": verlauf[-52:]}
