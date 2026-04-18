# Video Codec Project

**Course:** Multimedia-Kommunikation (AI1033)
**Term:** Summer Semester 2026
**Group:** [Gruppennummer]
**Members:** [Name 1], [Name 2], [Name 3], [Name 4]

------

## 1. Architecture

### 1.1 File Header

[Beschreibt hier den Aufbau eures Dateikopfs. Welche Metadaten speichert ihr (z. B. Auflösung, Framerate, Modus) und wie viele Bytes belegt jedes Feld?]

### 1.2 Frame Organization & Payload

[Wie sind die eigentlichen Bilddaten nach dem Header sortiert? Wie unterscheidet ihr zwischen Keyframes und Differenz-Frames? Skizziert hier kurz den Aufbau eures Bitstreams.]

------

## 2. Algorithms

### 2.1 Lossless Mode

- **Spatial Compression (Intra-frame):** [Welches Verfahren nutzt ihr innerhalb eines Bildes, um keine Informationen zu verlieren? (z. B. Vorhersage-Modelle oder verlustfreies RLE)]
- **Temporal Compression (Inter-frame):** [Wie nutzt ihr die Ähnlichkeit zwischen aufeinanderfolgenden Bildern aus, ohne Bit-Fehler zu riskieren?]

### 2.2 Lossy Mode

- **Spatial Compression (Intra-frame):** [Wo spart ihr hier massiv Daten ein? (z. B. Farbraum-Reduktion, Quantisierung oder Downsampling)]
- **Temporal Compression (Inter-frame):** [Wie geht ihr mit Bewegungen oder Änderungen zwischen Frames um, wenn Perfektion nicht das Ziel ist?]

------

## 3. Evaluation

### 3.1 Size Comparison

| **File / Mode**           | **File Size (Bytes / MB)** | **Compression Ratio** |
| ------------------------- | -------------------------- | --------------------- |
| **source.y4m (Original)** |                            | 1:1 (Reference)       |
| **Lossless (.bin)**       |                            |                       |
| **Lossy (.bin)**          |                            |                       |

[Beschreibt die Kompressionseigenschaften eures Codecs möglichst detailliert. Erläutert also nicht nur, dass komprimiert wird, sondern auch wie, an welchen Stellen besonders viele Daten eingespart werden und welche Auswirkungen das auf Dateigröße und Qualität hat.]

### 3.2 Visual Artifact Analysis

[Beschreibt hier ehrlich die Qualität eures Lossy-Ergebnisses. Treten Block-Artefakte, Farbrauschen oder "Geisterbilder" bei Bewegungen auf? Warum ist das so?]