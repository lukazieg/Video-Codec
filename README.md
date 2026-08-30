# Video Codec Project

**Course:** Multimedia-Kommunikation (AI1033)
**Term:** Summer Semester 2026
**Group:** 1
**Members:** Simon Merz, Jonas Pieper, Lukas Ziegler

------

## 1. Architecture
### 1.0 Magic Number
- The magic number is at the top of the Container. It is used to determine whether the container is Lossy (LY01) or Lossless (LS01)
 
### 1.1 File Header
[Beschreibt hier den Aufbau eures Dateikopfs. Welche Metadaten speichert ihr (z. B. Auflösung, Framerate, Modus) und wie viele Bytes belegt jedes Feld?]
- The file header is the same for Lossy and Lossless. It contains following information:
  | Field | Bytes | Description |
  | -------- | -------- | -------- |
  | width | 4 | Width of the video in pixels |
  | height | 4 | Height of the video in pixels |
  | fps | 4 + N | Framerate of the video |
  | interlacing | 4 + N | Determines if the frames are complete frames, halved frames or a mixture of both |
  | aspect_ratio | 4 + N | Ratio of width and height of each pixel (1:1 square) |
  | chroma | 4 + N | Determines the ratio between color and brightness (420jpeg is the only supported chroma in this pipeline) |
  
  (4 + N): The first 4 bytes store a number that tells you how many bytes follow (N). Those N bytes then contain the actual field value (as ASCII text).

### 1.2 Frame Organization & Payload
[Wie sind die eigentlichen Bilddaten nach dem Header sortiert? Wie unterscheidet ihr zwischen Keyframes und Differenz-Frames? Skizziert hier kurz den Aufbau eures Bitstreams.]
- This part of the bitstream differs between Lossless and Lossy. 
#### 1.2.1 Lossless
| Field | Bytes | Description |
| -------- | -------- | -------- |
| Huffman-Table | 4 + N * (4 + 1 + M) | Number of entries followed by N entries (each entry: i32 value + code length + Huffman Code) |
| #Frames | 4 | Number of frames |
| Length of image plane | #Frames * 12 | per frame: y_len, cb_len, cr_len |
| Payload length | 4 | Length of following payload |
| Payload | varies | Contains a huffman-encoded bitstream with all values of Y, Cb and Cr for each frame |

- Only the first frame of the Payload is an I-Frame, every other one is a P-Frame. This is not visible in the bitstream, instead it is hard coded in the encoding and decoding logic.
  The following 2 functions are responsible for this: temporal_predictive_compression, decode_temporal_compression.

#### 1.2.2 Lossy
| Field | Bytes | Description |
| -------- | -------- | -------- |
| #Frames | 4 | Number of frames |
| per Frame, per Plane (Y, Cb, Cr) | 4 + N | Plane length + N bytes |

------

## 2. Algorithms

### 2.1 Lossless Mode
- **Spatial Compression (Intra-frame):** [Welches Verfahren nutzt ihr innerhalb eines Bildes, um keine Informationen zu verlieren? (z. B. Vorhersage-Modelle oder verlustfreies RLE)]
 - The method used to achieve LosslessSC is Differential Pulse-Code Modulation. This means instead of storing all data for every pixel, only the difference to the previous pixel gets saved.
   This works well because neighbouring pixels in a picture are often similar which leads to small differential values.
   The values get stored in a 1D-Array with a set startvalue of 128 ([128, value1, value2,...]). This is done for each Plane, each with its own array.
   This method works well for Lossless Mode because its perfectly reversible by adding all the differences back together. 
   
- **Temporal Compression (Inter-frame):** [Wie nutzt ihr die Ähnlichkeit zwischen aufeinanderfolgenden Bildern aus, ohne Bit-Fehler zu riskieren?]
 - Lossless Temporal Compression stores the first frame completely, after that it only saves the differences for every pixel to the same pixel on the previous frame. 
   This achieves compression because you store smaller numbers. 
   To avoid bit-errors this is a purely integer operation with no rounding involved. It also makes the compression perfectly reversible so no data gets lost.

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
