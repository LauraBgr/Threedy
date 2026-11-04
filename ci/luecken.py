"""Lücken für Threedy: Vergleich mit allen Wettbewerbern und Empfehlungen der KI."""
import datetime as dt
import hashlib
import json

from . import ki
from .pfade import PROMPTS


def berechnen(firmen, texte, themen, cta_typen):
    """Vergleicht Threedy (referenz) mit allen Wettbewerbern: Themen, Keywords, CTAs, Belege, Presse."""
    ref = next((f for f in firmen if f["referenz"] and f["seiten"]), None)
    andere = [f for f in firmen if not f["referenz"] and f["seiten"]]
    if not ref or not andere:
        return {"referenz": None, "themen_tabelle": [], "keywords": [], "ctas": [], "belege": {}, "presse": {}, "themen": []}
    anteil = lambda f, t: f["themen"].get(t, 0) / max(1, len(f["seiten"]))
    tabelle = []
    for t in themen:
        nutzer = [f for f in andere if f["themen"].get(t)]
        ref_anteil = anteil(ref, t)
        wettb_anteil = sum(anteil(f, t) for f in andere) / len(andere)
        if not ref["themen"].get(t):
            status = "luecke" if len(nutzer) >= 2 else "offen"
        elif len(nutzer) <= 1:
            status = "staerke"
        elif ref_anteil < 0.5 * wettb_anteil:
            status = "schwach"
        else:
            status = "gleichauf"
        tabelle.append({"thema": t, "status": status, "threedy_seiten": ref["themen"].get(t, 0), "threedy_anteil": round(ref_anteil, 2),
                        "wettbewerber_anteil": round(wettb_anteil, 2), "firmen": [f["name"] for f in nutzer],
                        "eu": [f["name"] for f in nutzer if f["region"] == "EU"], "usa": [f["name"] for f in nutzer if f["region"] == "USA"],
                        "in_threedy_news": t in (ref.get("news_analyse") or {}).get("themen", []),
                        "news_firmen": [f["name"] for f in andere if t in (f.get("news_analyse") or {}).get("themen", [])]})
    reihenfolge = {"luecke": 0, "schwach": 1, "staerke": 2, "gleichauf": 3, "offen": 4}
    tabelle.sort(key=lambda z: (reihenfolge[z["status"]], -len(z["firmen"])))

    # Keywords: von mindestens 2 Wettbewerbern genutzt und auf keiner erfassten Threedy-Seite zu finden
    ref_text = texte.get(ref["name"], "")
    nutzer_kw = {}
    for f in andere:
        for k in {k for p in f["seiten"] for k in p["keywords"]}:
            nutzer_kw.setdefault(k, []).append(f)
    keywords = [{"keyword": k, "firmen": [f["name"] for f in fs], "eu": sum(f["region"] == "EU" for f in fs), "usa": sum(f["region"] == "USA" for f in fs)}
                for k, fs in nutzer_kw.items() if len(fs) >= 2 and len(k) > 2 and k not in ref_text]
    keywords.sort(key=lambda z: (-len(z["firmen"]), z["keyword"]))

    ctas = [{"typ": c, "firmen": [f["name"] for f in andere if f["cta_typen"].get(c)], "threedy": ref["cta_typen"].get(c, 0)} for c in cta_typen if c != "sonstiges"]
    ctas = [z for z in ctas if z["firmen"]]
    ctas.sort(key=lambda z: (z["threedy"] > 0, -len(z["firmen"])))

    belege = {feld: {"threedy": len(ref[feld]), "schnitt": round(sum(len(f[feld]) for f in andere) / len(andere), 1),
                     "spitze": max(andere, key=lambda f: len(f[feld]))["name"]} for feld in ("kunden", "belege", "branchen")}
    belege["beispiele"] = {f["name"]: f["belege"][:3] for f in andere if f["belege"]}

    grenze = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    zahl = lambda f: sum(1 for a in f.get("news", []) if (a.get("datum") or "") >= grenze and a.get("herkunft") != "Website")
    presse = {"threedy": zahl(ref), "schnitt": round(sum(zahl(f) for f in andere) / len(andere), 1),
              "je_firma": {f["name"]: zahl(f) for f in [ref] + andere},
              "threedy_ereignisse": len((ref.get("news_analyse") or {}).get("ereignisse", []))}
    return {"referenz": ref["name"], "anzahl_wettbewerber": len(andere), "themen_tabelle": tabelle, "keywords": keywords[:40],
            "ctas": ctas, "belege": belege, "presse": presse,
            "themen": [{"thema": z["thema"], "firmen": len(z["firmen"])} for z in tabelle if z["status"] == "luecke"]}


def empfehlungen(luecken, firmen, markt_analyse, cache, protokoll=print):
    """Eine KI-Anfrage: konkrete Empfehlungen aus der Lückenanalyse."""
    vorlage = (PROMPTS / "luecken_empfehlungen.md").read_text(encoding="utf-8")
    ref = firmen[luecken["referenz"]]
    daten = {
        "themes": [{k: z[k] for k in ("thema", "status", "threedy_anteil", "wettbewerber_anteil", "firmen", "in_threedy_news")} for z in luecken["themen_tabelle"]],
        "keyword_gaps": [{"keyword": z["keyword"], "used_by": z["firmen"]} for z in luecken["keywords"][:25]],
        "cta_types": luecken["ctas"], "proof_points": {k: v for k, v in luecken["belege"].items() if k != "beispiele"},
        "competitor_proof_examples": luecken["belege"]["beispiele"], "press_coverage_last_12_months": luecken["presse"],
        "threedy_messages": ref["hauptbotschaften"], "threedy_news": (ref.get("news_analyse") or {}).get("einordnung", ""),
        "competitor_messages": {f["name"]: f["hauptbotschaften"][:2] for f in firmen.values() if not f["referenz"] and f["seiten"]},
        "regions": {f["name"]: f["region"] for f in firmen.values()},
        "market_news": (markt_analyse or {}).get("einordnung", ""),
    }
    roh = json.dumps(daten, ensure_ascii=False)
    k = "luecken|" + hashlib.sha256((roh + vorlage + ki.konfiguration()["modell"]).encode()).hexdigest()[:20]
    if k in cache:
        return cache[k]
    try:
        a = ki.fragen(vorlage.replace("{daten}", roh))
    except Exception as ex:
        protokoll(f"   KI ! Empfehlungen: {ex}")
        return None
    emp = []
    for e in (a.get("empfehlungen") or [])[:8]:
        if isinstance(e, dict) and e.get("titel"):
            emp.append({"titel": str(e["titel"])[:120], "prioritaet": e.get("prioritaet") if e.get("prioritaet") in ("hoch", "mittel", "niedrig") else "mittel",
                        "art": str(e.get("art", ""))[:20], "begruendung": str(e.get("begruendung", ""))[:500],
                        "empfehlung": str(e.get("empfehlung", ""))[:500], "beispiel": str(e.get("beispiel", ""))[:300]})
    ergebnis = {"positionierung": str(a.get("positionierung", ""))[:800], "empfehlungen": emp,
                "nicht_verfolgen": [{"luecke": str(x.get("luecke", ""))[:150], "grund": str(x.get("grund", ""))[:300]}
                                    for x in (a.get("nicht_verfolgen") or [])[:3] if isinstance(x, dict)]}
    cache[k] = ergebnis
    protokoll("   KI ✓ Empfehlungen für Threedy")
    return ergebnis
