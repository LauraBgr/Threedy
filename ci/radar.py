"""Wettbewerber-Radar: neue Firmen in den Nachrichten erkennen, bewerten und bei hoher Gefahr automatisch beobachten.

Ablauf je Lauf:
1. Die KI liest Markt- und Wettbewerber-Artikel und nennt Firmen, die noch nicht beobachtet werden,
   mit Gefahr 1–5, Schlagwörtern und Begründung.
2. Das Programm zählt selbst, in wie vielen Artikeln der Name vorkommt (über alle Läufe).
3. Ist eine Firma ein Wettbewerber mit Gefahr >= min_gefahr und oft genug erwähnt, wird sie in
   data/auto_wettbewerber.json aufgenommen. Die offizielle Website kommt aus Wikidata.
   Ab dem nächsten Lauf werden Website und Nachrichten erfasst wie bei allen anderen Firmen.
Ausschließen: Namen unter radar.ausschliessen in config/wettbewerber.yaml eintragen.
"""
import datetime as dt
import hashlib
import json
import re
from urllib.parse import quote, urlparse

from . import ki
from .pfade import DATEN, PROMPTS, lies_json, schreib_json
from .sammeln import SITZUNG

AUTO = DATEN / "auto_wettbewerber.json"
RADAR = DATEN / "radar.json"
ARTEN = ("wettbewerber", "partner", "kunde", "investor", "sonstiges")


def norm(name):
    name = re.sub(r"\b(gmbh|ag|inc|corp|corporation|ltd|llc|se|sa|co|company|group|systems?|software|technologies|technology)\b\.?", "", name.lower())
    return re.sub(r"[^a-z0-9äöü]", "", name)


def einstellungen(cfg):
    r = cfg.get("radar") or {}
    return {"aktiv": r.get("aktiv", True), "automatisch": r.get("automatisch_hinzufuegen", True), "min_gefahr": r.get("min_gefahr", 4),
            "min_erwaehnungen": r.get("min_erwaehnungen", 2), "max_automatisch": r.get("max_automatisch", 6),
            "ausschliessen": [norm(n) for n in (r.get("ausschliessen") or [])]}


def auto_wettbewerber(cfg):
    """Automatisch aufgenommene Firmen (für __main__), ohne ausgeschlossene."""
    aus = einstellungen(cfg)["ausschliessen"]
    bekannt = {norm(w["name"]) for w in cfg["wettbewerber"]}
    return [w for w in lies_json(AUTO, []) if norm(w["name"]) not in aus and norm(w["name"]) not in bekannt]


def website(name):
    """Offizielle Website aus Wikidata (Eigenschaft P856). Leer, wenn nichts Passendes gefunden wird."""
    try:
        treffer = SITZUNG.get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&type=item&limit=5&search="
                              + quote(name), timeout=20).json().get("search", [])
        for t in treffer[:5]:
            ent = SITZUNG.get(f"https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims&ids={t['id']}", timeout=20).json()
            for c in ent["entities"][t["id"]].get("claims", {}).get("P856", []):
                url = c["mainsnak"].get("datavalue", {}).get("value", "")
                host = urlparse(url).netloc.lower()
                # Plausibel: ein Namensteil (mind. 4 Zeichen) steckt in der Domain
                if url and any(len(tl) >= 4 and tl in host for tl in re.findall(r"[a-z0-9]+", name.lower())):
                    return url
    except Exception:
        pass
    return ""


def pruefen(cfg, nachrichten, cache, mit_ki, protokoll=print):
    e = einstellungen(cfg)
    heute = dt.date.today().isoformat()
    radar = lies_json(RADAR, {}) or {}
    if not e["aktiv"]:
        return {"modus": "aus", "kandidaten": list(radar.values()), "aufgenommen": []}
    bekannte = [w["name"] for w in cfg["wettbewerber"]] + [x for w in cfg["wettbewerber"] for x in (w.get("aliase") or [])]
    artikel = []
    for name, n in nachrichten.items():
        artikel += [a for a in n["artikel"] if a.get("herkunft") != "Website"]
    artikel = sorted({a["titel"]: a for a in artikel}.values(), key=lambda a: a.get("datum") or "", reverse=True)[:150]
    alle_texte = [(a["titel"] + " " + a.get("auszug", "")).lower() for a in artikel]

    neu_gefunden = []
    if mit_ki and artikel:
        vorlage = (PROMPTS / "wettbewerber_finden.md").read_text(encoding="utf-8")
        zeilen = "\n".join(f"{i} | {a.get('datum') or '?'} | {a.get('quelle', '')} | {a.get('region', '')} | {a['titel']}"
                           + (f" | {a['auszug'][:200]}" if a.get("auszug") else "") for i, a in enumerate(artikel))
        gesperrt = bekannte + list((cfg.get("radar") or {}).get("ausschliessen") or [])
        k = "radar|" + hashlib.sha256((zeilen + vorlage + ",".join(gesperrt) + ki.konfiguration()["modell"]).encode()).hexdigest()[:20]
        antwort = cache.get(k)
        if antwort is None:
            try:
                antwort = ki.fragen(vorlage.replace("{bekannte}", ", ".join(gesperrt)).replace("{artikel}", zeilen))
                cache[k] = antwort
                protokoll(f"   KI ✓ Wettbewerber-Radar ({len(antwort.get('kandidaten') or [])} Kandidaten)")
            except Exception as ex:
                protokoll(f"   KI ! Wettbewerber-Radar: {ex}")
                antwort = {}
        bekannt_norm = {norm(b) for b in gesperrt}
        for c in (antwort.get("kandidaten") or [])[:12]:
            if not isinstance(c, dict) or not c.get("name") or norm(c["name"]) in bekannt_norm or len(norm(c["name"])) < 3:
                continue
            try:
                gefahr = max(1, min(5, int(c.get("gefahr", 1))))
            except (TypeError, ValueError):
                gefahr = 1
            quellen = []
            for i in c.get("artikel") or []:
                if isinstance(i, int) and 0 <= i < len(artikel):
                    a = artikel[i]; quellen.append({"titel": a["titel"], "link": a["link"], "datum": a.get("datum", ""), "quelle": a.get("quelle", "")})
            neu_gefunden.append({"name": str(c["name"])[:80], "art": c.get("art") if c.get("art") in ARTEN else "sonstiges",
                                 "region": c.get("region") if c.get("region") in ("EU", "USA", "andere") else "andere", "gefahr": gefahr,
                                 "produkt": str(c.get("produkt", ""))[:150], "begruendung": str(c.get("begruendung", ""))[:400],
                                 "schlagwoerter": [str(s)[:60] for s in (c.get("schlagwoerter") or [])][:6], "quellen": quellen[:5]})

    # In das Radar-Archiv übernehmen und Erwähnungen selbst zählen
    for c in neu_gefunden:
        k = norm(c["name"])
        alt = radar.get(k, {})
        laeufe = alt.get("laeufe", 0) + (1 if alt.get("zuletzt") != heute else 0)
        radar[k] = {**alt, **c, "erstmals": alt.get("erstmals", heute), "zuletzt": heute, "laeufe": laeufe or 1,
                    "quellen": (c["quellen"] + [q for q in alt.get("quellen", []) if q not in c["quellen"]])[:6],
                    "status": alt.get("status", "beobachtet")}
    for k, c in radar.items():
        treffer = sum(1 for t in alle_texte if c["name"].lower() in t)
        c["erwaehnungen"] = max(c.get("erwaehnungen", 0), treffer)
        if k in e["ausschliessen"]:
            c["status"] = "ausgeschlossen"

    # Automatisch aufnehmen
    auto = lies_json(AUTO, []) or []
    aufgenommen = []
    if e["automatisch"]:
        for k, c in sorted(radar.items(), key=lambda kv: (-kv[1]["gefahr"], -kv[1]["erwaehnungen"])):
            if len(auto) >= e["max_automatisch"]:
                break
            if (c["status"] == "beobachtet" and c["art"] == "wettbewerber" and c["gefahr"] >= e["min_gefahr"]
                    and c["erwaehnungen"] >= e["min_erwaehnungen"] and k not in {norm(a["name"]) for a in auto}):
                start = website(c["name"])
                auto.append({"name": c["name"], "region": "EU" if c["region"] == "EU" else "USA", "start": start, "sitemap": bool(start),
                             "news": [f'"{c["name"]}"'], "automatisch": True, "aufgenommen": heute,
                             "grund": f"Gefahr {c['gefahr']}/5, {c['erwaehnungen']} Erwähnungen: {c['begruendung']}"})
                c["status"] = "aufgenommen"; c["website"] = start
                aufgenommen.append(c["name"])
                protokoll(f"   Radar: {c['name']} automatisch aufgenommen (Gefahr {c['gefahr']}/5, Website: {start or 'nicht gefunden, nur News'})")
        schreib_json(AUTO, auto)
    schreib_json(RADAR, radar)
    kandidaten = sorted(radar.values(), key=lambda c: (c["status"] == "ausgeschlossen", -c["gefahr"], -c["erwaehnungen"]))
    return {"modus": "KI" if mit_ki else "aus (kein KI-Schlüssel)", "kandidaten": kandidaten, "aufgenommen": aufgenommen,
            "regeln": {k: e[k] for k in ("min_gefahr", "min_erwaehnungen", "max_automatisch", "automatisch")}}
