"""Nachrichten und Pressemeldungen sammeln und auswerten.

Quellen (alle frei zugänglich, ohne Schlüssel):
- Google News RSS (EU: deutsch/Deutschland, USA: englisch/USA)
- Bing News RSS (dieselben zwei Märkte)
- eigene Presse-, News- und Blogseiten der Firmen (über die Sitemap, robots.txt wird beachtet)

Artikel werden pro Firma archiviert: bekannte Artikel bleiben erhalten, neue werden markiert.
"""
import datetime as dt
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from . import ki
from .pfade import DATEN, PROMPTS, lies_json, schreib_json, slug
from .sammeln import SITZUNG, abrufen, sitemap_eintraege

MAERKTE = (  # region, Google-Parameter, Bing-Parameter
    ("EU", "hl=de&gl=DE&ceid=DE:de", "setlang=de-DE&cc=DE"),
    ("USA", "hl=en-US&gl=US&ceid=US:en", "setlang=en-US&cc=US"),
)
PRESSE_PFAD = re.compile(r"/(news|newsroom|press|presse|pressemitteilung|press-release|blog|aktuelles|stories|insights)(/|-|$)", re.I)
_letzter = {}


def _pause(host, sekunden=1.0):
    warten = sekunden - (time.time() - _letzter.get(host, 0))
    if warten > 0:
        time.sleep(warten)
    _letzter[host] = time.time()


def _text(html):
    return re.sub(r"\s+", " ", unescape(BeautifulSoup(html or "", "html.parser").get_text(" "))).strip()


def _datum(s):
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return ""


def _schluessel(titel):
    return re.sub(r"[^a-z0-9äöü]", "", titel.lower())[:70]


def _rss(url):
    _pause(urlparse(url).netloc)
    r = SITZUNG.get(url, timeout=20)
    r.raise_for_status()
    return ET.fromstring(r.content)


def google_news(suche, region, param):
    url = f"https://news.google.com/rss/search?q={quote_plus(suche)}&{param}"
    out = []
    for item in _rss(url).iter("item"):
        quelle = item.findtext("source") or ""
        titel = (item.findtext("title") or "").strip()
        if quelle and titel.endswith(" - " + quelle):
            titel = titel[: -len(quelle) - 3]
        auszug = _text(item.findtext("description"))
        if auszug.startswith(titel[:40]):     # Google liefert meist nur Titel + Quelle als Beschreibung
            auszug = ""
        out.append({"titel": titel, "link": item.findtext("link") or "", "quelle": quelle, "datum": _datum(item.findtext("pubDate")),
                    "auszug": auszug[:400], "region": region, "herkunft": "Google News", "suche": suche})
    return out


def bing_news(suche, region, param):
    url = f"https://www.bing.com/news/search?q={quote_plus(suche)}&format=rss&{param}"
    out = []
    for item in _rss(url).iter("item"):
        link = item.findtext("link") or ""
        ziel = parse_qs(urlparse(link).query).get("url")
        quelle = next((c.text for c in item if c.tag.lower().endswith("source") and c.text), "")
        out.append({"titel": (item.findtext("title") or "").strip(), "link": ziel[0] if ziel else link, "quelle": quelle or urlparse(ziel[0] if ziel else link).netloc,
                    "datum": _datum(item.findtext("pubDate")), "auszug": _text(item.findtext("description"))[:400],
                    "region": region, "herkunft": "Bing News", "suche": suche})
    return out


def suchen(begriffe, max_alter_tage, protokoll=print):
    """Alle Begriffe in allen Quellen und Märkten suchen, doppelte Artikel zusammenführen."""
    grenze = (dt.date.today() - dt.timedelta(days=max_alter_tage)).isoformat()
    gefunden, fehler = [], []
    for suche in begriffe:
        for region, g_param, b_param in MAERKTE:
            for quelle, f in (("Google News", google_news), ("Bing News", bing_news)):
                try:
                    gefunden += f(suche, region, g_param if f is google_news else b_param)
                except Exception as ex:
                    fehler.append(f"{quelle} {region} '{suche}': {str(ex)[:80]}")
    eindeutig = {}
    for a in sorted(gefunden, key=lambda a: (bool(a["auszug"]), a["datum"]), reverse=True):   # Einträge mit Auszug bevorzugen
        if not a["titel"] or (a["datum"] and a["datum"] < grenze):
            continue
        eindeutig.setdefault(_schluessel(a["titel"]), a)
    if fehler:
        protokoll(f"   ! {len(fehler)} News-Abfragen fehlgeschlagen, z. B. {fehler[0]}")
    return list(eindeutig.values()), fehler


def eigene_meldungen(start, pause, maximal=6):
    """Neueste Presse-, News- und Blogseiten der Firma selbst (Titel, Beschreibung, Datum)."""
    eintraege = [(u, m) for u, m in sitemap_eintraege(start, pause) if PRESSE_PFAD.search(urlparse(u).path) and urlparse(u).path.rstrip("/").count("/") >= 2]
    eintraege.sort(key=lambda x: x[1] or "", reverse=True)
    out = []
    for url, lastmod in eintraege[: maximal * 2]:
        if len(out) >= maximal:
            break
        try:
            soup = BeautifulSoup(abrufen(url, pause).text, "html.parser")
        except Exception:
            continue
        meta = lambda **k: (soup.find("meta", attrs=k) or {}).get("content", "") if soup.find("meta", attrs=k) else ""
        titel = meta(property="og:title") or (soup.title.get_text(strip=True) if soup.title else "")
        datum = (meta(property="article:published_time") or lastmod or "")[:10]
        out.append({"titel": titel[:200], "link": url, "quelle": "eigene Website", "datum": datum,
                    "auszug": (meta(name="description") or meta(property="og:description"))[:400], "herkunft": "Website", "region": ""})
    return out


def archivieren(datei, neu, heute, behalten=80):
    """Mit dem bisherigen Archiv zusammenführen; erstmals gefundene Artikel bekommen 'erstmals' = heute."""
    bisher = lies_json(datei, {}) or {}
    alt = {_schluessel(a["titel"]): a for a in bisher.get("artikel", [])}
    for a in alt.values():   # Archive aus älteren Versionen haben noch kein Funddatum
        a.setdefault("erstmals", bisher.get("abgerufen") or a.get("datum") or heute)
    for a in neu:
        k = _schluessel(a["titel"])
        a["erstmals"] = alt[k].get("erstmals", heute) if k in alt else heute
        alt[k] = a
    artikel = sorted(alt.values(), key=lambda a: a.get("datum") or a["erstmals"], reverse=True)[:behalten]
    return artikel


def sammeln(cfg, protokoll=print):
    """News für alle Firmen und den Markt. Wird von sammeln.sammeln() aufgerufen."""
    e = cfg["einstellungen"]
    heute = dt.date.today().isoformat()
    alter, maximal = e.get("news_max_alter_tage", 730), e.get("max_news_pro_firma", 40)
    ziele = [(w["name"], w.get("news"), w) for w in cfg["wettbewerber"]]
    markt = (cfg.get("markt") or {}).get("news")
    if markt:
        ziele.append(("_markt", markt, None))
    fehler = []
    for name, begriffe, w in ziele:
        begriffe = [begriffe] if isinstance(begriffe, str) else (begriffe or [])
        artikel, f = suchen(begriffe, alter, protokoll) if begriffe else ([], [])
        fehler += [{"firma": name, "url": "News", "fehler": x} for x in f[:3]]
        presse = []
        if w and w.get("sitemap"):
            try:
                presse = eigene_meldungen(w["start"], e["pause_sekunden"], e.get("max_eigene_meldungen", 6))
            except Exception as ex:
                fehler.append({"firma": name, "url": w["start"], "fehler": f"Presseseiten: {str(ex)[:120]}"})
        datei = DATEN / "news" / f"{slug(name)}.json"
        alle = archivieren(datei, artikel[:maximal] + presse, heute)
        neu = sum(1 for a in alle if a["erstmals"] == heute)
        schreib_json(datei, {"firma": name, "abgerufen": heute, "artikel": alle})
        protokoll(f"   News {name if name != '_markt' else 'Markt'}: {len(artikel)} Artikel, {len(presse)} eigene Meldungen, {neu} neu")
    return fehler


# ---------- Auswertung ----------

EREIGNIS_ARTEN = ["produkt", "partnerschaft", "kunde", "finanzierung", "uebernahme", "personal", "event", "studie", "sonstiges"]


def _bereinigen(a, themen):
    def liste(x, n):
        return [str(v).strip() for v in (x or []) if str(v).strip()][:n] if isinstance(x, list) else []
    ereignisse = []
    for ev in (a.get("ereignisse") or [])[:10]:
        if isinstance(ev, dict) and ev.get("beschreibung"):
            ereignisse.append({"datum": str(ev.get("datum", ""))[:10], "art": ev.get("art") if ev.get("art") in EREIGNIS_ARTEN else "sonstiges",
                               "beschreibung": str(ev["beschreibung"])[:300], "quelle": str(ev.get("quelle", ""))[:80]})
    return {"einordnung": str(a.get("einordnung", ""))[:800], "ereignisse": ereignisse,
            "themen": [t for t in liste(a.get("themen"), 20) if t in themen],
            "botschaften": liste(a.get("botschaften"), 6), "keywords": [k.lower() for k in liste(a.get("keywords"), 12)]}


def _ersatz(artikel, themen_muster):
    text = " ".join(a["titel"] + " " + a.get("auszug", "") for a in artikel).lower()
    return {"einordnung": "", "ereignisse": [], "botschaften": [], "keywords": [],
            "themen": [t for t, m in themen_muster.items() if len(re.findall(m, text)) >= 2]}


def auswerten(cfg, cache, themen, themen_muster, mit_ki, protokoll=print):
    """Gibt {firmenname: {'artikel': [...], 'analyse': {...}}} zurück, inkl. '_markt'."""
    vorlage = (PROMPTS / "news_auswerten.md").read_text(encoding="utf-8")
    pv = hashlib.sha256(vorlage.encode()).hexdigest()[:8]
    heute = dt.date.today().isoformat()
    namen = [(w["name"], w["region"]) for w in cfg["wettbewerber"]] + [("_markt", "EU und USA")]
    ergebnis = {}
    for name, region in namen:
        artikel = (lies_json(DATEN / "news" / f"{slug(name)}.json", {}) or {}).get("artikel", [])
        for a in artikel:
            a["neu"] = a.get("erstmals") == heute
        auswahl = artikel[:35]
        analyse = None
        if auswahl and mit_ki:
            liste = "\n".join(f"- {a.get('datum') or '?'} | {a.get('quelle', '')} | {a.get('region') or 'eigene Website'} | {a['titel']}"
                              + (f" | {a['auszug'][:250]}" if a.get("auszug") else "") for a in auswahl)
            k = "news|" + hashlib.sha256(liste.encode()).hexdigest()[:16] + f"|{ki.konfiguration()['modell']}|{pv}"
            analyse = cache.get(k)
            if analyse is None:
                gegenstand = "den Markt für industrielle 3D-Visualisierung, CAD/PLM-Viewer und digitale Zwillinge" if name == "_markt" else f"das Unternehmen „{name}“ (Region: {region})"
                try:
                    analyse = _bereinigen(ki.fragen(vorlage.replace("{gegenstand}", gegenstand).replace("{artikel}", liste)), themen)
                    cache[k] = analyse
                    protokoll(f"   KI ✓ News {name if name != '_markt' else 'Markt'}")
                except Exception as ex:
                    protokoll(f"   KI ! News {name}: {ex} → Ersatzmodus")
                    analyse = None
        if analyse is None:
            analyse = _ersatz(auswahl, themen_muster)
            analyse["ersatz"] = True
        ergebnis[name] = {"artikel": artikel, "analyse": analyse}
    return ergebnis
