"""Schnappschüsse mit der KI (oder im Ersatzmodus) auswerten und für das Dashboard zusammenfassen."""
import datetime as dt
import hashlib
import json
import re
from collections import Counter

from . import bewertung, ki, ki_sichtbarkeit, luecken as lueckenmodul, news, radar
from .pfade import DATEN, PROMPTS, lies_json, schreib_json, slug

THEMEN = ["browserbasiert", "streaming_grosser_daten", "multi_cad_formate", "design_review", "zusammenarbeit", "digitaler_zwilling",
          "ki_und_agenten", "ar_vr", "service_und_wartung", "fertigung_und_produktion", "vertrieb_und_marketing", "plm_integration",
          "sdk_und_api", "cloud_und_saas", "sicherheit_und_datenschutz", "skalierbarkeit_enterprise", "nachhaltigkeit", "kosten_und_roi"]
BELEG_ARTEN = ["kundenlogos", "fallstudie", "zahlen", "zertifikat", "auszeichnung", "partner", "enterprise", "sicherheit", "technische_tiefe", "roi"]
TOENE = ["technisch", "nutzen_und_roi", "visionaer", "vertrauen_und_sicherheit", "einfach_und_zugaenglich"]
CTA_TYPEN = ["demo", "testversion", "kontakt_vertrieb", "video", "dokumentation", "download", "event", "preise", "newsletter", "sonstiges"]

# Ersatzmodus: Stichwörter je Thema (englisch und deutsch)
THEMEN_MUSTER = {
    "browserbasiert": r"browser|web-based|webbasiert|no install|ohne installation|any device",
    "streaming_grosser_daten": r"stream|large (assembl|model|data)|massive|große datenmengen|lightweight|leichtgewicht",
    "multi_cad_formate": r"multi-?cad|\bformats?\b|formate|jt\b|step\b|catia|creo|nx\b|solidworks|interoperab",
    "design_review": r"design review|review|markup|annotation|measure|messen|vermess",
    "zusammenarbeit": r"collaborat|zusammenarbeit|share|teilen|team",
    "digitaler_zwilling": r"digital twin|digitaler zwilling|twin",
    "ki_und_agenten": r"\bai\b|\bki\b|agent|artificial intelligence|künstliche intelligenz|machine learning|generative",
    "ar_vr": r"\bar\b|\bvr\b|augmented|virtual reality|mixed reality|xr\b|spatial",
    "service_und_wartung": r"service|maintenance|wartung|aftersales|field",
    "fertigung_und_produktion": r"manufactur|fertigung|production|produktion|shop floor|factory|fabrik",
    "vertrieb_und_marketing": r"sales|vertrieb|marketing|configurator|konfigurator|e-?commerce",
    "plm_integration": r"\bplm\b|\berp\b|teamcenter|windchill|enovia|integration|integrat",
    "sdk_und_api": r"\bsdk\b|\bapi\b|developer|entwickler|toolkit",
    "cloud_und_saas": r"cloud|saas|on-?prem|kubernetes|microservice",
    "sicherheit_und_datenschutz": r"secur|sicherheit|datenschutz|gdpr|dsgvo|iso 27001|ip protection",
    "skalierbarkeit_enterprise": r"enterprise|scal|skalier|global|thousands",
    "nachhaltigkeit": r"sustainab|nachhaltig|co2|carbon",
    "kosten_und_roi": r"\broi\b|cost|kosten|save|einspar|faster|schneller|efficien|effizien",
}
CTA_MUSTER = {"demo": r"demo", "testversion": r"trial|free|testen|kostenlos|try", "kontakt_vertrieb": r"contact|kontakt|talk|sales|anfrage|get in touch",
              "video": r"video|watch|ansehen", "dokumentation": r"docs|documentation|dokumentation|learn more|mehr erfahren|read",
              "download": r"download|herunterladen", "event": r"event|webinar|register|anmelden", "preise": r"pricing|preise|price|buy|kaufen",
              "newsletter": r"newsletter|subscribe|abonnieren"}
STOPP = set("""the and for with your our you are from that this into more than can all how what why new get use using will have has their
our its was were been out also any only make made more most other over such them they very just about each which where when who
der die das und mit für von zu im in ist ein eine einer eines den dem des auf aus bei sich sie wir ihr ihre unser unsere oder als auch
nicht mehr wie was sind werden wird kann können zum zur über durch""".split())


def _liste(x, n=20):
    if isinstance(x, str):
        x = [x] if x.strip() else []
    return [str(v).strip() for v in (x or []) if str(v).strip()][:n]


def bereinigen(a):
    """Antwort der KI auf das feste Format bringen (fehlende Felder ergänzen, falsche Werte entfernen)."""
    return {
        "seitentyp": str(a.get("seitentyp", "sonstiges"))[:20],
        "sprache": str(a.get("sprache", ""))[:5],
        "hauptbotschaft": str(a.get("hauptbotschaft", ""))[:300],
        "ueberschriften": _liste(a.get("ueberschriften"), 5),
        "keywords": [k.lower() for k in _liste(a.get("keywords"), 15)],
        "themen": [t for t in _liste(a.get("themen")) if t in THEMEN],
        "ctas": _liste(a.get("ctas"), 10),
        "cta_typen": [c for c in _liste(a.get("cta_typen")) if c in CTA_TYPEN],
        "belege": _liste(a.get("belege"), 10),
        "kunden": _liste(a.get("kunden"), 15),
        "branchen": _liste(a.get("branchen"), 10),
        "zielgruppe": str(a.get("zielgruppe", ""))[:120],
        "differenzierung": str(a.get("differenzierung", ""))[:300],
        "wertversprechen": [w.lower() for w in _liste(a.get("wertversprechen"), 6)],
        "anwendungsfaelle": [w.lower() for w in _liste(a.get("anwendungsfaelle"), 6)],
        "keyword_arten": {k: [w.lower() for w in _liste((a.get("keyword_arten") or {}).get(k) if isinstance(a.get("keyword_arten"), dict) else [], 10)]
                          for k in ("kategorie", "produkt", "problem")},
        "beleg_arten": [b for b in _liste(a.get("beleg_arten")) if b in BELEG_ARTEN],
        "ton": a.get("ton") if a.get("ton") in TOENE else "",
        "klarheit": _zahl(a.get("klarheit")),
    }


def _zahl(x):
    try:
        return max(1, min(5, int(x)))
    except (TypeError, ValueError):
        return None


def synonyme_anwenden(cfg, firmen):
    """Ähnliche Begriffe zusammenfassen (config: keyword_synonyme), z. B. 'engineering review' -> 'design review'."""
    ziel = {}
    for haupt, liste in ((cfg.get("keyword_synonyme") or {}).items()):
        for v in liste or []:
            ziel[str(v).lower()] = str(haupt).lower()
    if not ziel:
        return
    for f in firmen.values():
        for p in f["seiten"]:
            for feld in ("keywords", "wertversprechen", "anwendungsfaelle"):
                p[feld] = list(dict.fromkeys(ziel.get(k, k) for k in p[feld]))
            p["keyword_arten"] = {k: list(dict.fromkeys(ziel.get(w, w) for w in v)) for k, v in p["keyword_arten"].items()}


def ersatz_auswertung(s):
    """Einfache Auswertung ohne KI, damit der Prototyp auch ohne Schlüssel läuft."""
    kopf = " ".join([s["titel"], s["beschreibung"], " ".join(s["ueberschriften"])])
    alles = (kopf + " " + s["text"]).lower()
    woerter = [w for w in re.findall(r"[a-zäöüß][a-zäöüß0-9\-]{2,}", kopf.lower()) if w not in STOPP]
    paare = [f"{a} {b}" for a, b in zip(woerter, woerter[1:])]
    kw = [k for k, _ in Counter(paare).most_common(8) if Counter(paare)[k] > 1] + [k for k, _ in Counter(woerter).most_common(15)]
    belege = re.findall(r"[^.]{0,80}(?:\d+\s?(?:%|x|times|mal|million|billion|customers|kunden)|trusted by|iso \d+|award)[^.]{0,60}", s["text"], re.I)
    return {
        "seitentyp": "startseite" if s["url"].rstrip("/").count("/") <= 3 else "produkt",
        "sprache": (s.get("sprache") or "")[:2],
        "hauptbotschaft": (s["ueberschriften"][0] if s["ueberschriften"] else s["titel"]),
        "ueberschriften": s["ueberschriften"][:5],
        "keywords": list(dict.fromkeys(kw))[:15],
        "themen": [t for t, m in THEMEN_MUSTER.items() if len(re.findall(m, alles)) >= 2],
        "ctas": s["cta_kandidaten"][:10],
        "cta_typen": [t for t, m in CTA_MUSTER.items() if any(re.search(m, c, re.I) for c in s["cta_kandidaten"])],
        "belege": [b.strip() for b in belege][:6],
        "kunden": [], "branchen": [], "zielgruppe": "", "differenzierung": "",
    }


def auswerten(cfg, protokoll=print):
    stand = lies_json(DATEN / "stand.json", {})
    lauf = lies_json(DATEN / "letzter_lauf.json", {"aenderungen": [], "fehler": []})
    vorlage = (PROMPTS / "seite_auswerten.md").read_text(encoding="utf-8")
    pv = hashlib.sha256(vorlage.encode()).hexdigest()[:8]   # Prompt geändert = Seiten neu auswerten
    texte = {}   # Firma -> gesamter Seitentext (für die Keyword-Lücken)
    mit_ki = ki.verfuegbar()
    modus = f"KI ({ki.konfiguration()['modell']})" if mit_ki else "Ersatzmodus ohne KI"
    protokoll(f"Auswertung im {modus}")
    cache = lies_json(DATEN / "analyse_cache.json", {})   # fingerabdruck+modus -> auswertung
    fehlversuche = 0   # nach 3 KI-Fehlern in Folge: Rest im Ersatzmodus, statt stundenlang zu warten
    firmen = {w["name"]: {"name": w["name"], "region": w["region"], "start": w.get("start", ""), "referenz": bool(w.get("referenz")),
                          "automatisch": bool(w.get("automatisch")), "seiten": []}
              for w in cfg["wettbewerber"]}
    aktuell_ab = (dt.date.today() - dt.timedelta(days=21)).isoformat()   # Seiten, die länger nicht mehr erfasst wurden, zählen nicht mehr
    for url, info in stand.items():
        if info["firma"] not in firmen or info.get("datum", "") < aktuell_ab:
            continue
        s = lies_json(DATEN / info["datei"])
        if not s:
            continue
        texte[info["firma"]] = texte.get(info["firma"], "") + " " + " ".join([s["titel"], s["beschreibung"], *s["ueberschriften"], s["text"]]).lower()
        schluessel = f"{info['fingerabdruck']}|{'ki:' + ki.konfiguration()['modell'] + '|' + pv if mit_ki else 'ersatz'}"
        a = cache.get(schluessel)
        if a is None:
            if mit_ki and fehlversuche < 3:
                prompt = (vorlage.replace("{firma}", s["firma"]).replace("{region}", s["region"]).replace("{url}", url)
                          .replace("{text}", f"TITEL: {s['titel']}\nBESCHREIBUNG: {s['beschreibung']}\nÜBERSCHRIFTEN: {' | '.join(s['ueberschriften'])}\n"
                                             f"BUTTONS/LINKS: {' | '.join(s['cta_kandidaten'])}\n\n{s['text'][:12000]}"))
                try:
                    a = bereinigen(ki.fragen(prompt))
                    fehlversuche = 0
                    protokoll(f"   KI ✓ {s['firma']}: {url}")
                    cache[schluessel] = a
                    schreib_json(DATEN / "analyse_cache.json", cache)   # sofort sichern, falls der Lauf abbricht
                except Exception as ex:
                    fehlversuche += 1
                    protokoll(f"   KI ! {url}: {ex} → Ersatzmodus")
                    if fehlversuche == 3:
                        protokoll("   KI antwortet nicht – restliche Seiten im Ersatzmodus (Schlüssel, Modellname und GWDG-Status prüfen)")
                    a = bereinigen(ersatz_auswertung(s)); a["ersatz"] = True   # nicht speichern: nächster Lauf fragt die KI erneut
            else:
                a = bereinigen(ersatz_auswertung(s)); a["ersatz"] = True
                if not mit_ki:
                    cache[schluessel] = a
        firmen[info["firma"]]["seiten"].append({"url": url, "region": info["region"], "datum": info["datum"], "titel": s["titel"], **a})
    schreib_json(DATEN / "analyse_cache.json", cache)

    # Zusammenfassen je Firma
    synonyme_anwenden(cfg, firmen)
    for f in firmen.values():
        kw, th, ct = Counter(), Counter(), Counter()
        for p in f["seiten"]:
            kw.update(p["keywords"]); th.update(p["themen"]); ct.update(p["cta_typen"])
        f.update(keywords=kw.most_common(25), themen=dict(th), cta_typen=dict(ct),
                 belege=list(dict.fromkeys(b for p in f["seiten"] for b in p["belege"]))[:15],
                 kunden=list(dict.fromkeys(k for p in f["seiten"] for k in p["kunden"]))[:20],
                 branchen=list(dict.fromkeys(b for p in f["seiten"] for b in p["branchen"]))[:15],
                 hauptbotschaften=[p["hauptbotschaft"] for p in f["seiten"] if p["hauptbotschaft"]][:4],
                 stand=max((p["datum"] for p in f["seiten"]), default=""),
                 wertversprechen=Counter(w for p in f["seiten"] for w in p.get("wertversprechen", [])).most_common(12),
                 anwendungsfaelle=Counter(w for p in f["seiten"] for w in p.get("anwendungsfaelle", [])).most_common(12),
                 keyword_arten={k: list(dict.fromkeys(w for p in f["seiten"] for w in p.get("keyword_arten", {}).get(k, [])))[:20] for k in ("kategorie", "produkt", "problem")},
                 beleg_arten=dict(Counter(b for p in f["seiten"] for b in p.get("beleg_arten", []))),
                 toene=dict(Counter(p["ton"] for p in f["seiten"] if p.get("ton"))),
                 klarheit=round(sum(k) / len(k), 1) if (k := [p["klarheit"] for p in f["seiten"] if p.get("klarheit")]) else None,
                 seiten_links=[{"url": p["url"], "titel": p["titel"], "seitentyp": p["seitentyp"], "datum": p["datum"]} for p in f["seiten"]][:8])
    nachrichten = news.auswerten(cfg, cache, THEMEN, THEMEN_MUSTER, mit_ki, protokoll)
    for f in firmen.values():
        n = nachrichten.get(f["name"], {"artikel": [], "analyse": {}})
        f.update(news=n["artikel"], news_analyse=n["analyse"])
    markt = nachrichten.get("_markt", {"artikel": [], "analyse": {}})
    schreib_json(DATEN / "analyse_cache.json", cache)
    radar_daten = radar.pruefen(cfg, nachrichten, cache, mit_ki, protokoll)
    schreib_json(DATEN / "analyse_cache.json", cache)

    sichtbarkeit = ki_sichtbarkeit.pruefen(cfg, cache, mit_ki, protokoll)
    schreib_json(DATEN / "analyse_cache.json", cache)

    # Lücken für Threedy
    luecken = lueckenmodul.berechnen(list(firmen.values()), texte, THEMEN, CTA_TYPEN)
    if mit_ki and luecken.get("referenz"):
        luecken["ki"] = lueckenmodul.empfehlungen(luecken, firmen, markt["analyse"], cache, protokoll)
        schreib_json(DATEN / "analyse_cache.json", cache)

    # Änderungsprotokoll fortschreiben
    log = lies_json(DATEN / "aenderungen.json", [])
    analyse_stand = lies_json(DATEN / "analyse_stand.json", {})   # url -> Auswertung beim letzten Lauf
    seiten_jetzt = {p["url"]: {k: p.get(k) for k in ("themen", "wertversprechen", "branchen", "cta_typen", "hauptbotschaft")}
                    for f in firmen.values() for p in f["seiten"]}
    for aend in lauf.get("aenderungen", []):
        if aend["art"] == "geändert":
            vorher = lies_json(DATEN / aend["vorher"], {}) or {}
            jetzt = lies_json(DATEN / stand[aend["url"]]["datei"], {}) or {}
            neu = [u for u in jetzt.get("ueberschriften", []) if u not in vorher.get("ueberschriften", [])]
            weg = [u for u in vorher.get("ueberschriften", []) if u not in jetzt.get("ueberschriften", [])]
            aend = dict(aend, neue_ueberschriften=neu[:8], entfernte_ueberschriften=weg[:8])
            alt_a, neu_a = analyse_stand.get(aend["url"], {}), seiten_jetzt.get(aend["url"], {})
            if alt_a and neu_a:
                diff = lambda feld: ([x for x in neu_a.get(feld, []) if x not in alt_a.get(feld, [])], [x for x in alt_a.get(feld, []) if x not in neu_a.get(feld, [])])
                for feld, name in (("themen", "themen"), ("wertversprechen", "aussagen"), ("branchen", "branchen"), ("cta_typen", "ctas")):
                    plus, minus = diff(feld)
                    if plus: aend[f"neue_{name}"] = plus[:6]
                    if minus: aend[f"entfernte_{name}"] = minus[:6]
                if alt_a.get("hauptbotschaft") and alt_a.get("hauptbotschaft") != neu_a.get("hauptbotschaft"):
                    aend["botschaft_vorher"], aend["botschaft_jetzt"] = alt_a["hauptbotschaft"], neu_a.get("hauptbotschaft", "")
        elif aend["art"] == "neu erfasst" and any(a.get("datum", "") < lauf.get("datum", "") for a in log):
            aend = dict(aend, art="neue Seite")   # nach der Erst-Erfassung neu aufgetauchte Seite
        log.insert(0, dict(aend, datum=lauf.get("datum", "")))
    log = log[:300]
    schreib_json(DATEN / "aenderungen.json", log)
    schreib_json(DATEN / "analyse_stand.json", seiten_jetzt)

    ergebnis = {"erstellt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "modus": modus,
                "firmen": list(firmen.values()), "luecken": luecken, "markt": markt, "radar": radar_daten, "ki_sichtbarkeit": sichtbarkeit,
                "scorecard": bewertung.scorecard(list(firmen.values()), log), "kpis": bewertung.kpis(cfg, list(firmen.values()), luecken, log, lauf.get("fehler", [])),
                "beleg_arten": BELEG_ARTEN, "toene": TOENE, "aenderungen": log[:60],
                "fehler": lauf.get("fehler", []), "themenliste": THEMEN, "cta_typen": CTA_TYPEN}

    # KI-Zusammenfassung
    if mit_ki:
        kurz = [{"firma": f["name"], "region": f["region"], "referenz": f["referenz"], "themen": f["themen"],
                 "keywords": [k for k, _ in f["keywords"][:12]], "cta": f["cta_typen"], "botschaften": f["hauptbotschaften"], "automatisch_aufgenommen": f.get("automatisch", False),
                 "wertversprechen": [w for w, _ in f.get("wertversprechen", [])[:6]], "ton": f.get("toene", {}),
                 "news": {"einordnung": f["news_analyse"].get("einordnung", ""), "ereignisse": f["news_analyse"].get("ereignisse", [])[:5]}} for f in firmen.values()]
        kurz.append({"markt_news": markt["analyse"]})
        if sichtbarkeit.get("aktiv"):
            kurz.append({"ki_antworten_sichtbarkeit": {f["firma"]: f["anteil"] for f in sichtbarkeit["firmen"]}})
        kurz.append({"luecken_fuer_threedy": [z["thema"] for z in luecken.get("themen_tabelle", []) if z["status"] in ("luecke", "schwach")],
                     "staerken_von_threedy": [z["thema"] for z in luecken.get("themen_tabelle", []) if z["status"] == "staerke"]})
        kurz.append({"neu_entdeckte_wettbewerber": [{"name": k["name"], "gefahr": k["gefahr"], "begruendung": k["begruendung"]} for k in radar_daten["kandidaten"] if k["gefahr"] >= 3][:6]})
        # Nur die Änderungen dieses Laufs; "neu erfasst" = erstmals beobachtet, keine Änderung durch die Firma
        art_en = {"neu erfasst": "first captured", "geändert": "changed", "neue Seite": "new page"}
        neue = [dict(a, art=art_en.get(a["art"], a["art"])) for a in lauf.get("aenderungen", [])]
        frueher = any(a.get("datum", "") < lauf.get("datum", "") for a in log)
        erster = bool(neue) and not frueher and all(a["art"] == "first captured" for a in neue)
        status = (f"FIRST_RUN ({sum(len(f['seiten']) for f in firmen.values())} pages, {len([f for f in firmen.values() if f['seiten']])} companies)"
                  if erster else "FOLLOW_UP_RUN")
        p = (PROMPTS / "zusammenfassung.md").read_text(encoding="utf-8").replace("{daten}", json.dumps(kurz, ensure_ascii=False)) \
            .replace("{laufstatus}", status) \
            .replace("{aenderungen}", json.dumps(neue[:40], ensure_ascii=False) if neue else "none")
        try:
            ergebnis["zusammenfassung"] = ki.fragen(p, json_antwort=False)
        except Exception as ex:
            ergebnis["zusammenfassung"] = f"(Summary failed: {ex})"
    else:
        ergebnis["zusammenfassung"] = ""
    schreib_json(DATEN / "ergebnis.json", ergebnis)
    return ergebnis
