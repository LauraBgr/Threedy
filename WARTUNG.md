# Wartungsanleitung

Für das Marketing-Team von Threedy, nachdem das Projektteam nicht mehr dabei ist. Für die meisten Aufgaben ist kein Programmieren nötig: Man ändert eine Textdatei direkt auf GitHub (Stift-Symbol → „Commit changes“).

## Einen Wettbewerber hinzufügen oder entfernen

Datei `config/wettbewerber.yaml` öffnen und einen Block ergänzen:

```yaml
  - name: Neue Firma
    region: USA                 # oder EU
    start: https://www.neue-firma.com/
    sitemap: true               # Produktseiten automatisch finden
    seiten:                     # optional: feste Seiten
      - {url: https://www.neue-firma.com/de/produkt, region: EU, sprache: de}
    news: '"Neue Firma" 3D'     # Suchbegriff für Nachrichten
```

Entfernen: Block löschen. Die alten Daten bleiben im Verlauf erhalten.

## Was die KI auswertet, ändern

- `prompts/seite_auswerten.md`: welche Felder die KI pro Seite füllt. Die **Themenliste** dort muss mit `THEMEN` in `ci/auswerten.py` übereinstimmen, wenn man ein Thema ergänzt.
- `prompts/zusammenfassung.md`: Aufbau und Länge der wöchentlichen Zusammenfassung.

Nach einer Änderung am Prompt wertet der nächste Lauf alle Seiten neu aus.

## Den KI-Anbieter wechseln

Der GWDG-Zugang gehört zum Studierendenkonto und endet mit dem Projekt. Jeder Anbieter mit OpenAI-kompatibler Schnittstelle funktioniert ohne Codeänderung. Es reicht, die drei Secrets zu ändern (Settings → Secrets and variables → Actions):

| Anbieter | `KI_BASIS_URL` | `KI_MODELL` (Beispiel) |
|---|---|---|
| GWDG | `https://chat-ai.academiccloud.de/v1` | `qwen3.5-397b-a17b` (Liste: `python -m ci modelle`) |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Mistral (EU) | `https://api.mistral.ai/v1` | `mistral-small-latest` |
| Azure OpenAI / eigene Server | Adresse laut Anbieter | laut Anbieter |

Ohne gültigen Schlüssel läuft der Ersatzmodus weiter, das Dashboard zeigt dann oben einen Hinweis.

## Häufigere Abläufe

| Wunsch | Wo |
|---|---|
| Lauf sofort starten | Actions → Wöchentliche Wettbewerbsanalyse → Run workflow |
| Rhythmus ändern (z. B. alle 2 Wochen) | `.github/workflows/woechentlich.yml`, Zeile `cron` |
| mehr Seiten pro Firma | `config/wettbewerber.yaml` → `max_seiten_pro_firma` |
| Ältere Schnappschüsse | werden automatisch gelöscht, es bleiben die letzten 8 je Seite |

## Wenn etwas nicht funktioniert

| Meldung | Bedeutung | Lösung |
|---|---|---|
| Mail „Run failed“ von GitHub | Lauf abgebrochen | Actions → fehlgeschlagener Lauf → roten Schritt öffnen und Meldung lesen |
| Dashboard → Quellen: „404“ | Seite gibt es nicht mehr | neue Adresse in `wettbewerber.yaml` eintragen |
| „robots.txt verbietet den Abruf“ | Website erlaubt keine automatischen Abrufe | Seite weglassen oder von Hand prüfen |
| „kaum Text auf der Seite“ | Inhalt wird nur per JavaScript geladen | andere Unterseite eintragen (z. B. Produktseite statt Startseite) |
| „KI-Anfrage fehlgeschlagen“ | Schlüssel abgelaufen, Kontingent leer oder Anbieter gestört | Secrets prüfen, Anbieter wechseln. Bis dahin Ersatzmodus |
| Hinweis „Ersatzmodus“ im Dashboard | kein KI-Schlüssel hinterlegt | Secret `KI_SCHLUESSEL` setzen |

## Ergebnisse richtig lesen

- **Themen-Tracker:** zählt Seiten. Firmen mit mehr erfassten Seiten haben automatisch höhere Zahlen. Für faire Vergleiche ähnlich viele Seiten pro Firma eintragen.
- **Lücken für Threedy:** Themen und Keywords, die mindestens zwei Wettbewerber nutzen, Threedy aber auf seinen erfassten Seiten nicht. Das ist ein Hinweis, keine Empfehlung: Manche Lücken sind bewusst.
- **Änderungen:** gezählt werden geänderte Titel, Beschreibungen, Überschriften und Buttons, nicht jeder kleine Textunterschied.
