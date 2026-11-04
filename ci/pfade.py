import json
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEN = WURZEL / "data"
DOCS = WURZEL / "docs"
PROMPTS = WURZEL / "prompts"
CONFIG = WURZEL / "config" / "wettbewerber.yaml"


def lies_json(pfad, standard=None):
    try:
        return json.loads(Path(pfad).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return standard


def schreib_json(pfad, daten):
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(pfad)


def slug(text):
    s = re.sub(r"^https?://", "", text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or "x"
