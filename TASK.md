# Ausarbeitung Multimedia-Kommunikation

**Modul:** Multimedia-Kommunikation (AI1033)
**Semester:** Sommersemester 2026 
**Thema:** Entwicklung eines einfachen Video-Encoders und -Decoders  
**Gruppengröße:** 3 bis 4 Personen

---

## 1. Ausgangssituation

Für dieses Projekt steht euch bereits ein kleines Grundgerüst zur Verfügung. Als einzige Eingabequelle verwendet ihr die Datei `source.y4m`.

Bitte ladet zunächst die bereitgestellte Projektvorlage sowie die Datei `source.y4m` herunter und seht euch das zugehörige Einführungsvideo an. Folgt anschließend den Anweisungen in dieser Datei (`TASK.md`) und bearbeitet die Programmieraufgabe innerhalb des vorgegebenen Scaffolds.

```text
.
├── .python-version    # Python-Version für den Paketmanager 'uv'
├── DECLARATION.md     # Vorlage für Eigenständigkeit & KI-Offenlegung
├── main.py            # Funktionsfähiges Grundgerüst
├── pyproject.toml     # Konfigurationsdatei für 'uv'
├── README.md          # Vorlage für die technische Dokumentation
├── source.y4m         # Das offizielle Testvideo (wird separat bereitgestellt)
└── TASK.md            # Diese Aufgabenstellung
```

Das bereitgestellte `main.py` übernimmt bereits das Einlesen und Schreiben von Y4M-Dateien sowie den groben Ablauf der beiden Pipelines. Eure Hauptaufgabe besteht also darin, innerhalb dieses Scaffolds die eigentliche **Kompressions- und Dekompressionslogik** für den **Lossless-** und **Lossy-Modus** zu implementieren und verständlich zu dokumentieren.

Die Datei `source.y4m` kann [hier](https://mmnet.informatik.hs-fulda.de/aomanalyzer/source.y4m) heruntergeladen werden und gehört **nicht zur Abgabe**. Bitte verwendet für Entwicklung und Test diese offizielle Datei. Bei der Korrektur wird dieselbe `source.y4m` in das Abgabeverzeichnis gelegt und eure Pipeline anschließend ausgeführt.

## 2. Gewünschter Ablauf

Das Programm soll vollständig automatisiert mit [uv](https://docs.astral.sh/uv/) über den Befehl `uv run main.py` ausführbar sein.
Ohne zusätzliche Benutzereingabe soll die Pipeline dabei folgende Schritte durchlaufen:

1. **Input:** Einlesen der `source.y4m` aus dem Hauptverzeichnis
2. **Setup:** Automatisches Erstellen des Zielverzeichnisses `output/`
3. **Lossless Pipeline:** Kompression der Frames in eine `.bin`-Datei und anschließende Dekompression in eine im VLC Player abspielbare `.y4m`-Datei
4. **Lossy Pipeline:** Kompression der Frames in eine `.bin`-Datei und anschließende Dekompression in eine im VLC Player abspielbare `.y4m`-Datei

*Hinweis:* Sobald bei einem Verarbeitungsschritt Informationen verändert werden (z. B. durch Rundungsfehler bei einer Umwandlung wie YCbCr → RGB), ist das Ergebnis nicht mehr vollständig lossless.

------

## 3. Fachliche Kernideen

Für eine gelungene Ausarbeitung sollen im Code die beiden folgenden Grundideen der Kompression erkennbar umgesetzt werden:

- **Spatial Compression (Intra-frame):** Reduktion von Redundanzen **innerhalb eines einzelnen Bildes**
  (z. B. durch Run-Length Encoding oder Residual-Quantisierung)
- **Temporal Compression (Inter-frame):** Reduktion von Redundanzen **zwischen aufeinanderfolgenden Bildern**
  (z. B. durch Frame Differencing)

Wichtig ist dabei vor allem, dass eure gewählten Verfahren **fachlich sinnvoll**, **nachvollziehbar implementiert** und in der Dokumentation **verständlich erklärt** sind.
Es geht also nicht darum, möglichst komplexe Verfahren zu bauen, sondern die zugrunde liegenden Konzepte klar und sauber umzusetzen.

------

## 4. Hinweise zur Implementierung

- **Eigenleistung:**
  Die Kompressions- und Dekompressionslogik soll von euch selbst implementiert werden.
  Das bereitgestellte Scaffold dürft und sollt ihr selbstverständlich verwenden. Die eigentliche Codec-Logik sollte jedoch klar als eure eigene Arbeit erkennbar sein.
  Externe Tools oder Bibliotheken, die die Kompressionslogik bereits im Wesentlichen fertig mitbringen (z. B. **FFMPEG**, `zlib`, `gzip` oder vergleichbare High-Level-Wrapper), sind für diesen Teil der Aufgabe nicht vorgesehen.
- **Fortschrittsanzeige:**
  Da die Verarbeitung je nach Implementierung spürbar Zeit in Anspruch nehmen kann, soll das Programm den aktuellen Fortschritt der Pipeline durch eine Fortschrittsanzeige sichtbar machen. Hierfür kann z. B. eine kleine Konsolenausgabe oder eine Bibliothek wie `tqdm` verwendet werden.
- **Code-Stil:**
  Der gesamte Code soll in **englischer Sprache** verfasst werden. Achtet auf aussagekräftige Benennungen, klare Strukturen und **selbsterklärenden Code**. Als Referenz für den erwarteten Code-Stil dient dieses [Video](https://www.youtube.com/watch?v=Bf7vDBBOBUA) von CodeAesthetic.
- **KI-Nutzung:**
  Der unterstützende Einsatz von KI-Tools ist erlaubt, muss aber in der `DECLARATION.md` **transparent und ehrlich** dokumentiert werden. Diese Offenlegung ist Teil der Prüfungsleistung.

------

## 5. Dokumentation

Bitte ergänzt in der **README.md** die folgenden technischen Abschnitte (in **englischer Sprache**):

- **Architecture:**
  Beschreibung des von euch verwendeten Binärformats bzw. der Struktur eures Bitstreams innerhalb des bereitgestellten Scaffolds
  (z. B. Header-Felder, Organisation der Payload, Kennzeichnung unterschiedlicher Frame-Typen)
- **Algorithms:**
  Erläuterung eurer **Spatial-** und **Temporal-Strategien** für beide Modi
- **Evaluation:**
  Tabellarischer Vergleich der Dateigrößen von Originalvideo (`source.y4m`) und den erzeugten Binärdateien (Lossless und Lossy), inklusive Angabe der Kompressionsrate. Zusätzlich eine kurze Beschreibung der im Lossy-Modus sichtbaren visuellen Artefakte (z. B. Unschärfe, Blockbildung, Detailverlust) und deren mögliche Ursachen in der Implementierung.

In der **DECLARATION.md** dokumentiert ihr zusätzlich die Beiträge der einzelnen Teammitglieder sowie die Nutzung von KI-Unterstützung.

------

## 6. Abgabe

Die Einreichung erfolgt als ZIP-Datei.
Zur Korrektur wird die offizielle `source.y4m` in das Verzeichnis gelegt und anschließend eure Pipeline gestartet.

**Die ZIP-Datei sollte dabei wie folgt aufgebaut sein:**

```text
submission.zip
├── DECLARATION.md
├── README.md
├── main.py
└── pyproject.toml
```

*Bitte beachtet:* Die Datei `source.y4m` gehört **nicht** in die Abgabe.

Auch **unvollständige, aber lauffähige Lösungen** werden bewertet. Teilpunkte gibt es für korrekt implementierte Teilfunktionen.

Eine **erneute Abgabe ist bis zur angegebenen Deadline jederzeit möglich**.

------

## 7. Bewertung

| **Bereich**               | **Gewichtung** | **Kriterien**                                               |
| ------------------------- | -------------- | ----------------------------------------------------------- |
| **Code & Implementation** | **2/3**        | Algorithmen-Logik, Funktionalität, Clean Code               |
| **Documentation**         | **1/3**        | Technische Tiefe der README und Korrektheit der DECLARATION |

### Bewertungshinweis und Leistungsniveaus:
Die Bewertung richtet sich nicht nach der absoluten Effizienz oder visuellen Qualität der Kompression. Maßgeblich sind vielmehr die fachlich sinnvolle, nachvollziehbare und robuste Umsetzung der grundlegenden Kompressionsprinzipien, die Funktionsfähigkeit der Pipeline sowie die Qualität von Code, Dokumentation und Evaluation. Eine einfache, aber sauber umgesetzte und gut erklärte Lösung kann daher ausdrücklich sehr gut bewertet werden.

**Wichtig:** Eine einfache, stabile I-/P-Frame-Lösung ohne Motion Estimation, B-Frames oder sonstige komplexe Prädiktionsverfahren liegt vollständig im Erwartungshorizont. Zusätzliche Komplexität führt nicht automatisch zu einer besseren Bewertung. **Eine einfache, aber sauber umgesetzte Lösung kann mit sehr gut bewertet werden.**

#### Ausreichend bis befriedigend:
Die Lösung ist insgesamt funktionsfähig, weist jedoch kleinere Mängel im Code oder in der Umsetzung auf. Die geforderten Grundideen sind erkennbar umgesetzt, die Dokumentation ist jedoch eher knapp, teilweise ungenau oder nicht durchgehend überzeugend. Insgesamt handelt es sich um eine solide, aber noch nicht vollständig ausgereifte Leistung.

#### Gut:
Die Lösung ist robust und fachlich sinnvoll implementiert. Die gewählten Verfahren sind nachvollziehbar umgesetzt, der Code ist überwiegend sauber strukturiert und die Pipeline funktioniert zuverlässig. Die Dokumentation ist ordentlich und verständlich, auch wenn sie in einzelnen Punkten noch nicht die volle technische Tiefe erreicht. Insgesamt ist dies eine überzeugende und klar über dem Mindestniveau liegende Leistung.

#### Sehr gut:
Die Lösung ist robust, sauber und fachlich überzeugend implementiert. Der Code ist klar strukturiert, nachvollziehbar und zuverlässig ausführbar. Die Dokumentation geht deutlich über das Mindestmaß hinaus, erläutert Architektur und Algorithmen präzise und enthält eine herausragende, einsichtsreiche Evaluation, die die Ergebnisse kritisch reflektiert und fachlich einordnet. Insgesamt handelt es sich um eine besonders gelungene Leistung.