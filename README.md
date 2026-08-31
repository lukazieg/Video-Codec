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
| Huffman-Table | 4 + N * (4 + 1 + M) | Number of entries followed by N entries (each entry: i32 value + code length + M (Huffman Code)) |
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
| #Levels | 4 | Number of quantization levels |
| Length of image plane | #Frames * 12 | per frame: y_len, cb_len, cr_len |
| Payload length | 4 | Length of following payload in bytes |
| Payload | varies | Quantized values for all Y, Cb and Cr values of each frame |

------

## 2. Algorithms

### 2.1 Lossless Mode
- **Spatial Compression (Intra-frame):** 
  - The method used to achieve LosslessSC is Differential Pulse-Code Modulation. This means instead of storing all data for every pixel, only the difference to the previous pixel gets saved.
   This works well because neighbouring pixels in a picture are often similar which leads to small differential values.
   The values get stored in a 1D-Array with a set startvalue of 128 ([128, value1, value2,...]). This is done for each Plane, each with its own array.
   This method works well for Lossless Mode because its perfectly reversible by adding all the differences back together. 
   
- **Temporal Compression (Inter-frame):** 
  - Our implementation of Lossless Temporal Compression stores the first frame completely, after that it only saves the differences for every pixel to the same pixel on the previous frame. 
   This achieves compression because the stored numbers are smaller. It also works on top of our Spatial Compression to enhance the encoding even further because the similarities over time are getting encoded as well. Since a lot of these differences are close to 0 it also increases the effectiveness of the Huffman encoding by increasing the number of values that only need a short code instead of a long one. 
   Because each frame builds upon its previous ones and each pixel on its previous, there can not be any rounding of values to avoid changing the later values. It also makes the compression perfectly reversible so no data gets lost.

- **Huffman Coding:**
  - Spatial and Temporal Compression alone doesn't shrink the file size. The actual reduction only happens in combination with Huffman coding. 
   Huffman assigns codes to each residual value after the compression. The length of the codes varies depending on how often they occur, so having less variety of values to usually encode means much less code length needed. 

### 2.2 Lossy Mode

- **Spatial Compression (Intra-frame):** 
   - Lossy Spatial Compression uses quantization, this means that each 8-bit pixel value (0-255) is mapped into one of 64 buckets (value // step, step = 256 // levels).
    This reduces the number of possible pixel values from 256 (8-bit) to 64 (6-bit) which in turn saves storage space, because the bitstream uses 6-bit instead of 8-bit values.  
    When decoding each bucket is approximated by its middle value (quantized * step + step // 2), which minimizes rounding errors. 

- **Temporal Compression (Inter-frame):** 
  - Lossy Temporal Compression deletes every second frame during encoding, the remaining frames get packed into the bitstream. 
    During decoding the missing frames are reconstructed, using the averages of the previous and next frame for each pixel (current_pixel + last_pixel) // 2.
    Since the last frame doesn't have a next frame, the second to last frame gets duplicated and put into that spot. 
------

## 3. Evaluation

### 3.1 Size Comparison

| **File / Mode**           | **File Size (Bytes / MB)** | **Compression Ratio** |
| ------------------------- | -------------------------- | --------------------- |
| **source.y4m (Original)** | 405.002                    | 1:1 (Reference)       |
| **Lossless (.bin)**       | 92.977                     | 4,36:1                |
| **Lossy (.bin)**          | 151.877                    | 2,67:1                |

### 3.1.1 Lossless Mode
 - Lossless Mode achieves compression through 3 combined steps, spatial and temporal prediction and Huffman coding. The predictions reduce most pixel values close to 0. This makes Huffman coding extremely efficient.
  The compression rate is 4,36:1. In addition the compression and decompression is completely lossless meaning every pixel is 100% reconstructed.
  Static or very similar parts of the video are where compression is highest, while fast changing parts don't achieve very high compression.

### 3.1.2 Lossy Mode
 - Lossy Mode achieves compression through 2 separate steps. First every second frame gets deleted which leads to 50% fewer frames. Then every pixel value of the remaining frames gets reduced from 8-bit to 6-bit.
  Unlike Lossless Mode, lossy's compression isn't impacted by video content. The compression rate is 2,67:1 and there is a visible drop in quality which you can see when watching the reduced video.

### 3.2 Visual Artifact Analysis

[Beschreibt hier ehrlich die Qualität eures Lossy-Ergebnisses. Treten Block-Artefakte, Farbrauschen oder "Geisterbilder" bei Bewegungen auf? Warum ist das so?]
