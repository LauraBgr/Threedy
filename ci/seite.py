"""Baut das Dashboard als einzelne statische Seite docs/index.html (für GitHub Pages)."""
import json

from .pfade import DATEN, DOCS, WURZEL, lies_json


def bauen():
    daten = lies_json(DATEN / "ergebnis.json")
    if not daten:
        raise SystemExit("Keine Daten. Erst `python -m ci sammeln` und `python -m ci auswerten` ausführen.")
    vorlage = (WURZEL / "ci" / "vorlage.html").read_text(encoding="utf-8")
    roh = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(vorlage.replace("/*DATEN*/null", roh), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    return DOCS / "index.html"
