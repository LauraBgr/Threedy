"""Scorecard nach den festen Bewertungskriterien und die KPIs aus dem Projektdokument."""
import datetime as dt


def _rel(wert, maximum):
    """1 bis 5 relativ zum besten Wert aller Firmen."""
    return 1 + round(4 * wert / maximum) if maximum else 1


def scorecard(firmen, log):
    """Ein Wert 1–5 je Firma und Kriterium, mit kurzer Begründung (für den Tooltip)."""
    liste = [f for f in firmen if f["seiten"]]
    kw = {f["name"]: len({k for p in f["seiten"] for k in p["keywords"]}) for f in liste}
    bel = {f["name"]: len(f["belege"]) + len(f["kunden"]) + 2 * len(f.get("beleg_arten", {})) for f in liste}
    aend = {f["name"]: sum(1 for a in log if a["firma"] == f["name"] and a["art"] in ("geändert", "neue Seite")) for f in liste}
    zeilen = []
    for f in liste:
        typen = {p["seitentyp"] for p in f["seiten"]}
        artikel = [a for a in f.get("news", []) if a.get("herkunft") != "Website"]
        eigene = [a for a in f.get("news", []) if a.get("herkunft") == "Website"]
        sprachen = {(p.get("sprache") or "")[:2] for p in f["seiten"] if p.get("sprache")}
        punkte = min(2, len(typen) / 2) + (len(artikel) >= 5) + bool(eigene) + (len(sprachen) > 1)
        if len(sprachen) > 1:
            gruppen = {}
            for p in f["seiten"]:
                gruppen.setdefault((p.get("sprache") or "")[:2], set()).update(p["themen"] + p.get("wertversprechen", []))
            werte = list(gruppen.values())
            unterschied = len(set.union(*werte) - set.intersection(*werte))
            regional, r_text = 3 + min(2, unterschied // 3), f"{len(sprachen)} language versions, {unterschied} differing themes/claims"
        else:
            regional, r_text = 1, "only one language version captured"
        ctas = len(f["cta_typen"])
        zeilen.append({"firma": f["name"], "region": f["region"], "referenz": f["referenz"], "werte": {
            "abdeckung": [min(5, 1 + round(punkte)), f"{len(typen)} page types, {len(artikel)} articles, {len(eigene)} own press items, {len(sprachen)} languages"],
            "keywords": [_rel(kw[f["name"]], max(kw.values())), f"{kw[f['name']]} distinct keywords"],
            "klarheit": [round(f["klarheit"]) if f.get("klarheit") else None, f"AI rating {f.get('klarheit') or '–'} of 5 (average over pages)"],
            "belege": [_rel(bel[f["name"]], max(bel.values())), f"{len(f['belege'])} proof points, {len(f['kunden'])} named customers, {len(f.get('beleg_arten', {}))} proof types"],
            "regional": [regional, r_text],
            "cta": [min(5, max(1, ctas)), f"{ctas} CTA types"],
            "aenderungen": [min(5, 1 + aend[f["name"]]), f"{aend[f['name']]} changes or new pages detected"],
        }})
    return {"kriterien": [["abdeckung", "Source coverage"], ["keywords", "Keyword visibility"], ["klarheit", "Messaging clarity"], ["belege", "Proof points"],
                          ["regional", "Regional variation"], ["cta", "CTA strategy"], ["aenderungen", "Change activity"]], "zeilen": zeilen}


def kpis(cfg, firmen, luecken, log, fehler):
    andere = [f for f in firmen if f["seiten"] and not f["referenz"]]
    eu = [f for f in andere if f["region"] == "EU"]
    us = [f for f in andere if f["region"] == "USA"]
    anteil = lambda g, t: sum(1 for f in g if f["themen"].get(t)) / len(g) if g else 0
    themen = {t for f in andere for t in f["themen"]}
    wiederkehrend = sorted(t for t in themen if sum(1 for f in andere if f["themen"].get(t)) >= 2)
    claims = {}
    for f in andere:
        for w, _ in f.get("wertversprechen", []):
            claims.setdefault(w, set()).add(f["name"])
    claims_wdh = [w for w, fs in claims.items() if len(fs) >= 2]
    regional = sorted(t for t in themen if abs(anteil(eu, t) - anteil(us, t)) >= 0.34)
    t_luecken = [z["thema"] for z in luecken.get("themen_tabelle", []) if z["status"] in ("luecke", "schwach")]
    cta_luecken = [c["typ"] for c in luecken.get("ctas", []) if not c["threedy"] and len(c["firmen"]) >= 2]
    kw_luecken = luecken.get("keywords", [])
    empf = len(((luecken.get("ki") or {}).get("empfehlungen")) or [])
    takt = (cfg.get("einstellungen") or {}).get("rhythmus", "weekly (Mondays)")
    return [
        {"name": "Competitors tracked", "wert": len(andere), "detail": f"{len(eu)} EU · {len(us)} USA", "definition": "Count of competitors actively monitored across Europe and the United States."},
        {"name": "Keywords per competitor", "wert": round(sum(len({k for p in f["seiten"] for k in p["keywords"]}) for f in andere) / max(1, len(andere)), 1),
         "detail": "average distinct keywords", "definition": "Number of meaningful keywords, keyword phrases and category terms captured for each competitor."},
        {"name": "Recurring messaging themes", "wert": len(wiederkehrend) + len(claims_wdh), "detail": f"{len(wiederkehrend)} themes + {len(claims_wdh)} value claims used by ≥ 2 competitors",
         "definition": "Count of repeated positioning themes identified across competitor materials."},
        {"name": "Regional differences", "wert": len(regional), "detail": "themes with ≥ 34 pt EU/USA difference", "definition": "Number of clear differences found between EU and US messaging or keyword strategy.", "liste": regional},
        {"name": "Gaps for Threedy", "wert": len(t_luecken) + len(cta_luecken) + min(10, len(kw_luecken)), "detail": f"{len(t_luecken)} themes · {len(cta_luecken)} CTA types · {min(10, len(kw_luecken))} keywords · {empf} AI recommendations",
         "definition": "Number of actionable whitespace opportunities identified for messaging, SEO or paid media."},
        {"name": "Update frequency", "wert": takt, "detail": f"last run {dt.date.today().isoformat()} · {len(fehler)} capture errors", "definition": "How often the dashboard, dataset and change log are refreshed."},
    ]
