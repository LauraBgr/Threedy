"""Aufruf: python -m ci [alles|sammeln|auswerten|seite|modelle]"""
import os
import sys
from pathlib import Path

import yaml

from .pfade import CONFIG, WURZEL


def lade_env():
    """Lokale Einstellungen aus .env (auf GitHub kommen sie aus den Secrets)."""
    p = WURZEL / ".env"
    if p.exists():
        for zeile in p.read_text(encoding="utf-8").splitlines():
            if "=" in zeile and not zeile.strip().startswith("#"):
                k, v = zeile.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    lade_env()
    befehl = sys.argv[1] if len(sys.argv) > 1 else "alles"
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    from . import auswerten, ki, radar, sammeln, seite
    cfg["wettbewerber"] += radar.auto_wettbewerber(cfg)   # vom Radar automatisch aufgenommene Firmen
    if befehl == "modelle":
        for m in ki.modelle():
            print(m)
        return
    if befehl in ("alles", "sammeln"):
        lauf = sammeln.sammeln(cfg)
        print(f"Gesammelt: {lauf['seiten']} Seiten, {len(lauf['aenderungen'])} Änderungen, {len(lauf['fehler'])} Fehler")
    if befehl in ("alles", "auswerten"):
        e = auswerten.auswerten(cfg)
        print(f"Ausgewertet: {sum(len(f['seiten']) for f in e['firmen'])} Seiten ({e['modus']})")
    if befehl in ("alles", "seite"):
        print("Dashboard:", seite.bauen())
    # Exit-Code 1, wenn viele Seiten fehlschlagen → GitHub schickt eine Fehlermail
    from .pfade import DATEN, lies_json
    lauf = lies_json(DATEN / "letzter_lauf.json", {})
    if befehl in ("alles", "sammeln") and lauf and lauf.get("seiten", 0) == 0:
        sys.exit("Keine einzige Seite abgerufen – bitte Quellen und Netzwerk prüfen.")


if __name__ == "__main__":
    main()
