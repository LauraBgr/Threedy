# Wartungsanleitung

Für das Marketing-Team von Threedy, nachdem das Projektteam nicht mehr dabei ist. Für fast alle Aufgaben ist kein Programmieren nötig: Man ändert eine Textdatei direkt auf GitHub (Stift-Symbol → „Commit changes“). Der nächste Lauf übernimmt die Änderung.

## Was jede Woche automatisch passiert

| Schritt | Was | Wo einstellbar |
|---|---|---|
| 1. Webseiten | Startseite, feste Seiten und über die Sitemap gefundene Produkt-, Lösungs-, Preis- und Vergleichsseiten jeder Firma | `config/wettbewerber.yaml` |
| 2. Nachrichten | Google News und Bing News (EU deutsch, USA englisch), eigene Presse- und Blogseiten der Firmen, Markt-News | `news:` je Firma, `markt:` |
| 3. Seitenauswertung | KI liest jede Seite mit festem Prompt: Botschaft, Wertversprechen, Keywords (Kategorie/Produkt/Problem), Themen, CTAs, Belege und Belegarten, Branchen, Ton, Klarheit | `prompts/seite_auswerten.md` |
| 4. News-Auswertung | KI fasst die Presse je Firma zusammen: Ereignisse, Themen, Botschaften | `prompts/news_auswerten.md` |
| 5. Wettbewerber-Radar | KI erkennt neue Firmen in den Nachrichten und bewertet die Gefahr (1–5); gefährliche werden automatisch beobachtet | `radar:`, `prompts/wettbewerber_finden.md` |
| 6. KI-Sichtbarkeit (AISEO) | Typische Käuferfragen an die KI; gezählt wird, welche Anbieter sie nennt | `ki_sichtbarkeit:` |
| 7. Lücken und Empfehlungen | Vergleich Threedy ↔ Wettbewerber, KI schlägt konkrete Maßnahmen vor | `prompts/luecken_empfehlungen.md` |
| 8. Änderungen | Vergleich mit dem Vorlauf: neue/entfernte Aussagen, Themen, Branchen, CTAs, Überschriften, neue Seiten | automatisch |
| 9. Zusammenfassung | What changed, Why it matters, Market patterns, EU vs. USA, What Threedy should do next | `prompts/zusammenfassung.md` |
| 10. Dashboard | wird neu gebaut und auf GitHub Pages veröffentlicht | automatisch |

## Einen Wettbewerber hinzufügen oder entfernen

Datei `config/wettbewerber.yaml` öffnen und einen Block ergänzen:

```yaml
  - name: Neue Firma
    region: USA                 # oder EU
    start: https://www.neue-firma.com/
    sitemap: true               # Produkt-, Lösungs-, Preis- und Vergleichsseiten automatisch finden
    seiten:                     # optional: feste Seiten, z. B. die deutsche Version
      - {url: https://www.neue-firma.com/de/produkt, region: EU, sprache: de}
    news: ['"Neue Firma" 3D', '"Produktname"']   # Suchbegriffe für Nachrichten
    aliase: [Produktname]       # weitere Namen, an denen die Firma in KI-Antworten erkannt wird
```

Entfernen: Block löschen. Die alten Daten bleiben im Verlauf erhalten.

## Wettbewerber-Radar (automatisch neue Wettbewerber)

Die KI liest jede Woche alle Markt- und Wettbewerber-Artikel und nennt Firmen, die noch nicht beobachtet werden, mit Gefahr 1–5, Schlagwörtern und Begründung. Eine Firma wird **automatisch aufgenommen**, wenn sie ein Wettbewerber ist, die Gefahr mindestens `min_gefahr` beträgt und sie in mindestens `min_erwaehnungen` Artikeln vorkommt. Die Website kommt aus Wikidata. Wird keine gefunden, beobachtet das Programm nur die Nachrichten.

| Wunsch | Was tun |
|---|---|
| Firma soll nie aufgenommen werden | Namen unter `radar: ausschliessen:` eintragen (wirkt auch nachträglich) |
| strengere oder lockerere Regeln | `min_gefahr`, `min_erwaehnungen`, `max_automatisch` ändern |
| nur vorschlagen, nicht aufnehmen | `automatisch_hinzufuegen: false` |
| aufgenommene Firma dauerhaft und sauber pflegen | als normalen Block in `wettbewerber.yaml` übernehmen (Website, Suchbegriffe prüfen) |

Die automatisch aufgenommenen Firmen stehen in `data/auto_wettbewerber.json`. Im Dashboard tragen sie den Hinweis „Added by radar“.

## Begriffe vereinheitlichen

Unter `keyword_synonyme:` werden Varianten zusammengefasst, z. B. zählen „collaborative review“ und „engineering review“ als „design review“. Einfach neue Zeilen ergänzen.

## Sichtbarkeit in KI-Antworten (AISEO)

Unter `ki_sichtbarkeit: fragen:` stehen die Käuferfragen, die der KI jede Woche gestellt werden. Fragen an aktuelle Kampagnen anpassen, englisch und deutsch gemischt ist sinnvoll. Wichtig für die Auswertung: Das Modell antwortet aus seinem Trainingswissen und sucht nicht live im Netz. Der Wert zeigt also, wie präsent eine Marke im Wissen von KI-Assistenten ist, und ist vor allem im Verlauf über die Wochen aussagekräftig. Ein Modellwechsel verändert die Werte.

## Was die KI auswertet, ändern

- In den Dateien im Ordner `prompts/` stehen die Anweisungen an die KI als normaler Text.
- Die **Themenliste** in `seite_auswerten.md` und `news_auswerten.md` muss mit `THEMEN` in `ci/auswerten.py` übereinstimmen, wenn man ein Thema ergänzt (einzige Stelle mit Code).
- Nach einer Änderung an `seite_auswerten.md` wertet der nächste Lauf alle Seiten neu aus.

## Den KI-Anbieter wechseln

Der GWDG-Zugang gehört zum Studierendenkonto und endet mit dem Projekt. Jeder Anbieter mit OpenAI-kompatibler Schnittstelle funktioniert ohne Codeänderung. Es reicht, die drei Secrets zu ändern (Settings → Secrets and variables → Actions):

| Anbieter | `KI_BASIS_URL` | `KI_MODELL` (Beispiel) |
|---|---|---|
| GWDG | `https://chat-ai.academiccloud.de/v1` | `qwen3-30b-a3b-instruct-2507` (Liste: `python -m ci modelle`) |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Mistral (EU) | `https://api.mistral.ai/v1` | `mistral-small-latest` |
| Azure OpenAI / eigene Server | Adresse laut Anbieter | laut Anbieter |

Große, langsame Modelle können das Zeitlimit von 2 Minuten pro Anfrage überschreiten. Dann ein kleineres Modell wählen. Ohne gültigen Schlüssel läuft der Ersatzmodus weiter. News-Auswertung, Radar, Empfehlungen und KI-Sichtbarkeit fehlen dann, und das Dashboard zeigt oben einen Hinweis.

## Änderungsalarme richtig lesen (Ansicht „Changes“)

| Art | Bedeutung | Was tun |
|---|---|---|
| First captured | Seite wurde zum ersten Mal erfasst (Grundstand) | nichts |
| New page | nach dem Grundstand neu aufgetauchte Seite (z. B. neues Produkt, neue Branche) | Seite ansehen: neue Positionierung? |
| Changed: Main message | Hauptaussage der Seite ist anders | häufig ein Repositionierungs-Signal |
| Changed: Themes / Value claims | neue oder entfernte Themen und Nutzenversprechen | mit eigener Botschaft vergleichen |
| Changed: Industries | neue oder entfernte Zielbranchen | Branchenstrategie prüfen |
| Changed: CTA types | andere Handlungsaufforderung, z. B. plötzlich „Free trial“ | Angebotsstrategie prüfen |
| Changed: Headings | nur Überschriften anders | meist kleine Textpflege |

Kleine Textänderungen im Fließtext lösen bewusst keinen Alarm aus.

## Häufige Abläufe

| Wunsch | Wo |
|---|---|
| Lauf sofort starten | Actions → Wöchentliche Wettbewerbsanalyse → Run workflow |
| Rhythmus ändern (z. B. alle 2 Wochen) | `.github/workflows/woechentlich.yml`, Zeile `cron`, und `rhythmus` in der YAML für die Anzeige |
| mehr Seiten pro Firma | `max_seiten_pro_firma` |
| andere Seitenarten bevorzugen | `seiten_stichworte` |
| mehr oder ältere Artikel | `max_news_pro_firma`, `news_max_alter_tage` |
| Dashboard an neue Marktprioritäten anpassen | Themenliste (siehe oben), Käuferfragen, Markt-Suchbegriffe, Radar-Regeln |
| ältere Schnappschüsse | werden automatisch gelöscht, es bleiben die letzten 8 je Seite |

## Wenn etwas nicht funktioniert

| Meldung | Bedeutung | Lösung |
|---|---|---|
| Mail „Run failed“ von GitHub | Lauf abgebrochen | Actions → fehlgeschlagener Lauf → roten Schritt öffnen und Meldung lesen |
| Dashboard → Sources: „404“ | Seite gibt es nicht mehr | neue Adresse in `wettbewerber.yaml` eintragen |
| „blocked by robots.txt“ | Website erlaubt keine automatischen Abrufe | Seite weglassen oder von Hand prüfen |
| „almost no text“ | Inhalt wird nur per JavaScript geladen | andere Unterseite eintragen |
| „KI-Anfrage fehlgeschlagen … timed out“ | Modell zu langsam oder überlastet | kleineres Modell in `KI_MODELL` |
| „KI-Anfrage fehlgeschlagen … 401/403“ | Schlüssel abgelaufen oder ungültig | Secret `KI_SCHLUESSEL` erneuern |
| „News-Abfragen fehlgeschlagen“ | Nachrichtenquelle kurz nicht erreichbar | meist von selbst behoben; sonst Suchbegriff prüfen |
| Hinweis „Fallback mode“ im Dashboard | kein KI-Schlüssel hinterlegt | Secret `KI_SCHLUESSEL` setzen |

## Ergebnisse richtig lesen

- **Scorecard:** die festen Bewertungskriterien aus dem Projektauftrag, für alle Firmen gleich berechnet. Die meisten Werte sind relativ zur besten Firma. Die Begründung steht im Tooltip.
- **Themen-Heatmap:** Anteil der erfassten Seiten. Firmen mit wenigen Seiten haben schnell 0 % oder 100 %. Für faire Vergleiche ähnlich viele Seiten pro Firma eintragen.
- **Gaps for Threedy:** „Gap“ heißt, mindestens zwei Wettbewerber nutzen das Thema und Threedy gar nicht. „Under-weighted“ heißt, Threedy nutzt es auf weniger als halb so vielen Seiten wie der Schnitt. „Strength“ heißt, Threedy nutzt es und höchstens ein Wettbewerber auch. Die Empfehlungen sind Vorschläge der KI, keine Entscheidungen.
- **Radar:** Die Gefahr bewertet die KI aus Schlagzeilen und Auszügen, eine kurze Prüfung durch einen Menschen ist sinnvoll.
- **Nicht abgedeckt:** Anzeigen-Bibliotheken von LinkedIn und Google sowie Suchergebnisseiten haben keine offene Schnittstelle bzw. verbieten automatische Abrufe. Sie sind deshalb bewusst nicht automatisiert und können bei Bedarf von Hand ergänzt werden.
