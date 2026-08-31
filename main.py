from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
import struct

from tqdm import tqdm
from PIL import Image

SOURCE_FILE = Path("source.y4m")
OUTPUT_DIR = Path("output")

LOSSLESS_BIN_FILE = OUTPUT_DIR / "lossless.bin"
LOSSLESS_Y4M_FILE = OUTPUT_DIR / "lossless_reconstructed.y4m"

LOSSY_BIN_FILE = OUTPUT_DIR / "lossy.bin"
LOSSY_Y4M_FILE = OUTPUT_DIR / "lossy_reconstructed.y4m"


# ============================================================================
# Data model
# Students edit: no | purpose: store metadata and decoded frame planes.
# ============================================================================

@dataclass
class Y4MMetadata:
    width: int
    height: int
    fps: str
    interlacing: str
    aspect_ratio: str
    chroma: str

    @property
    def y_plane_size(self) -> int:
        return self.width * self.height

    @property
    def uv_plane_size(self) -> int:
        if self.chroma != "420jpeg":
            raise ValueError("This scaffold only supports C420jpeg")
        return (self.width // 2) * (self.height // 2)


@dataclass
class Frame:
    y: bytes
    cb: bytes
    cr: bytes


# ============================================================================
# File system
# Students edit: no | purpose: create the output directory.
# ============================================================================

def ensure_output_directory() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Y4M I/O
# Students edit: no | purpose: read input Y4M and write reconstructed Y4M.
# ============================================================================

def parse_y4m_header(header_line: str) -> Y4MMetadata:
    parts = header_line.strip().split()

    if not parts or parts[0] != "YUV4MPEG2":
        raise ValueError("Invalid Y4M header")

    values: dict[str, str] = {
        "F": "25:1",
        "I": "p",
        "A": "1:1",
        "C": "420jpeg",
    }

    for part in parts[1:]:
        values[part[0]] = part[1:]

    if "W" not in values or "H" not in values:
        raise ValueError("Missing width or height in Y4M header")

    return Y4MMetadata(
        width=int(values["W"]),
        height=int(values["H"]),
        fps=values["F"],
        interlacing=values["I"],
        aspect_ratio=values["A"],
        chroma=values["C"],
    )


def read_y4m(path: Path) -> tuple[Y4MMetadata, list[Frame]]:
    with path.open("rb") as file:
        metadata = parse_y4m_header(file.readline().decode("ascii"))
        frames: list[Frame] = []

        while True:
            frame_marker = file.readline()
            if not frame_marker:
                break

            if not frame_marker.startswith(b"FRAME"):
                raise ValueError("Invalid frame marker in Y4M file")

            y = file.read(metadata.y_plane_size)
            cb = file.read(metadata.uv_plane_size)
            cr = file.read(metadata.uv_plane_size)

            if len(y) != metadata.y_plane_size:
                raise ValueError("Unexpected end of file while reading Y plane")
            if len(cb) != metadata.uv_plane_size:
                raise ValueError("Unexpected end of file while reading Cb plane")
            if len(cr) != metadata.uv_plane_size:
                raise ValueError("Unexpected end of file while reading Cr plane")

            frames.append(Frame(y=y, cb=cb, cr=cr))

    return metadata, frames


def write_y4m(path: Path, metadata: Y4MMetadata, frames: list[Frame]) -> None:
    header = (
        f"YUV4MPEG2 "
        f"W{metadata.width} "
        f"H{metadata.height} "
        f"F{metadata.fps} "
        f"I{metadata.interlacing} "
        f"A{metadata.aspect_ratio} "
        f"C{metadata.chroma}\n"
    )

    with path.open("wb") as file:
        file.write(header.encode("ascii"))

        for frame in frames:
            file.write(b"FRAME\n")
            file.write(frame.y)
            file.write(frame.cb)
            file.write(frame.cr)


# ============================================================================
# Bitstream I/O
# Students edit: no | purpose: save and load encoded binary data.
# ============================================================================

def write_bitstream(path: Path, bitstream: bytes) -> None:
    path.write_bytes(bitstream)


def read_bitstream(path: Path) -> bytes:
    return path.read_bytes()


# ============================================================================
# Binary helpers
# Students edit: no | purpose: simplify custom container parsing.
# ============================================================================

class ByteReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def read_bytes(self, length: int) -> bytes:
        chunk = self.data[self.offset:self.offset + length]
        if len(chunk) != length:
            raise ValueError("Unexpected end of bitstream")
        self.offset += length
        return chunk

    def read_u32(self) -> int:
        return struct.unpack("<I", self.read_bytes(4))[0]

    def read_text(self) -> str:
        return self.read_bytes(self.read_u32()).decode("ascii")


def append_u32(buffer: bytearray, value: int) -> None:
    buffer.extend(struct.pack("<I", value))


def append_text(buffer: bytearray, value: str) -> None:
    encoded = value.encode("ascii")
    append_u32(buffer, len(encoded))
    buffer.extend(encoded)


def pack_metadata(buffer: bytearray, metadata: Y4MMetadata) -> None:
    append_u32(buffer, metadata.width)
    append_u32(buffer, metadata.height)
    append_text(buffer, metadata.fps)
    append_text(buffer, metadata.interlacing)
    append_text(buffer, metadata.aspect_ratio)
    append_text(buffer, metadata.chroma)


def unpack_metadata(reader: ByteReader) -> Y4MMetadata:
    return Y4MMetadata(
        width=reader.read_u32(),
        height=reader.read_u32(),
        fps=reader.read_text(),
        interlacing=reader.read_text(),
        aspect_ratio=reader.read_text(),
        chroma=reader.read_text(),
    )


# ============================================================================
# Student helpers
# Students edit: yes | purpose: add helper functions for your codec.
# ============================================================================
@dataclass
class SignedFrame:
    y: list[int]
    cb: list[int]
    cr: list[int]


def single_color_inter_frame_prediction(current_colors: list[int], next_colors: list[int]) -> list[int]:
    pixel_amount = len(current_colors)
    y_temporal_differences = []
    for pixel_index in range(pixel_amount):
        temporally_next_pixel = next_colors[pixel_index]
        current_pixel = current_colors[pixel_index]
        difference = temporally_next_pixel - current_pixel
        y_temporal_differences.append(difference)
    return y_temporal_differences


def temporal_predictive_compression(signed_frames: list[SignedFrame]) -> list[SignedFrame]:
    temporal_compressed_frames = [signed_frames[0]]  # starting frame
    frames_amount = len(signed_frames)
    for frame_index in tqdm(range(frames_amount - 1), total=frames_amount, initial=1, file=sys.stdout):
        y_predictions = single_color_inter_frame_prediction(signed_frames[frame_index].y,
                                                            signed_frames[frame_index + 1].y)
        cb_predictions = single_color_inter_frame_prediction(signed_frames[frame_index].cb,
                                                             signed_frames[frame_index + 1].cb)
        cr_predictions = single_color_inter_frame_prediction(signed_frames[frame_index].cr,
                                                             signed_frames[frame_index + 1].cr)
        temporal_compressed_frames.append(SignedFrame(y=y_predictions, cb=cb_predictions, cr=cr_predictions))
    return temporal_compressed_frames


def decode_single_color_inter_frame_prediction(current_colors: list[int], next_colors: list[int]) -> list[int]:
    pixel_amount = len(current_colors)
    y_temporal_differences = []
    for pixel_index in range(pixel_amount):
        temporally_next_pixel = next_colors[pixel_index]
        current_pixel = current_colors[pixel_index]
        original_value = temporally_next_pixel + current_pixel
        y_temporal_differences.append(original_value)
    return y_temporal_differences


def decode_temporal_compression(temporal_frames: list[SignedFrame]) -> list[SignedFrame]:
    last_frame = temporal_frames[0]
    frames = [last_frame]
    for frame_index in tqdm(range(1, len(temporal_frames)), total=len(temporal_frames), initial=1, file=sys.stdout):
        previous_frame = frames[frame_index - 1]
        current_frame = temporal_frames[frame_index]
        y_originals = decode_single_color_inter_frame_prediction(previous_frame.y, current_frame.y)
        cb_originals = decode_single_color_inter_frame_prediction(previous_frame.cb, current_frame.cb)
        cr_originals = decode_single_color_inter_frame_prediction(previous_frame.cr, current_frame.cr)
        frames.append(SignedFrame(y=y_originals, cb=cb_originals, cr=cr_originals))
    return frames


def encode_predictive_compression(colors: bytes, starting_color: int) -> list[int]:
    compressed_colors = [starting_color]
    previous_color = starting_color
    for i in range(0, len(colors)):
        difference = colors[i] - previous_color
        previous_color = colors[i]
        compressed_colors.append(difference)
    return compressed_colors  # format: starting_value_128 difference_0 difference_1 difference_2 ...


def decode_predictive_compression(differences: list[int]) -> list[int]:
    colors = []
    starting_color = differences[0]
    previous_color = starting_color
    for i in range(1, len(differences)):
        color = previous_color + differences[i]
        previous_color = color
        colors.append(color)
    return colors


def predictive_compression_efficiency_test(metadata: Y4MMetadata, frames: list[Frame]) -> list[int]:
    print_metadata(metadata, frames[0])
    print(encode_predictive_compression(metadata, frames[0].y))
    for i in range(20):
        print(len(encode_predictive_compression(metadata, frames[i].y)))
        print(len(encode_predictive_compression(metadata, frames[i].cb)))
        print(len(encode_predictive_compression(metadata, frames[i].cr)))


def temporal_run_length_encoding(frames: list[list[int]]) -> list[list[int]]:
    trle_encoding = []
    for x in range(1, len(frames[0])):
        last_color = frames[0][x]
        repetition = 1
        trle_encoding_pixel = [frames[0][x]]
        for frame in frames[1:]:
            color = frame[x]
            if color == last_color:
                repetition += 1
            else:
                trle_encoding_pixel.append(repetition)
                trle_encoding_pixel.append(last_color)
                repetition = 1
                last_color = color
        trle_encoding_pixel.append(repetition)
        trle_encoding_pixel.append(last_color)
        trle_encoding.append(trle_encoding_pixel)
    return trle_encoding


def encode_trle(frames: list[SignedFrame]) -> tuple[list[list[int]], list[list[int]], list[list[int]]]:
    # trle = temporal run-length encoding
    # Encodes how often a color repeats between frames for each pixel: amount_of_repetition color_value
    # If two frames have the same SignedFrame Value at the same pixel its written 2 Signed_pixel_value.
    # Each row in the list hold all signed pixel values for the entire video for a single pixel
    y_frames = []
    cb_frames = []
    cr_frames = []
    for frame in frames:
        y_frames.append(frame.y)
        cb_frames.append(frame.cb)
        cr_frames.append(frame.cr)

    encoded_y_frames = temporal_run_length_encoding(y_frames)
    encoded_cb_frames = temporal_run_length_encoding(cb_frames)
    encoded_cr_frames = temporal_run_length_encoding(cr_frames)
    print(encoded_y_frames[0])
    # encoded_y_frames format: list of temporal_pixels each holding amount_0 difference_0 amount_1 difference_1 etc.
    return encoded_y_frames, encoded_cb_frames, encoded_cr_frames


def calc_frame_count(single_pixel_trle: list[int]) -> int:
    frame_count = 0
    for i in range(1, len(single_pixel_trle), 2):
        repetition = single_pixel_trle[i]
        frame_count += repetition
    return frame_count


def decode_single_trle_color(color_frames: list[list[int]]) -> list[list[int]]:
    frame_count = calc_frame_count(color_frames[0])
    frames = []
    print(color_frames[0])
    for frame_index in range(frame_count):
        colors = []
        starting_color = color_frames[0][frame_index]
        colors.append(starting_color)
        for pixel_index in range(1, len(color_frames), 2):
            repetition = color_frames[pixel_index][frame_index]
            color = color_frames[pixel_index + 1][frame_index]
            for _ in range(repetition):
                colors.append(color)
            colors.append(color_frames[pixel_index][frame_index])
        frames.append(colors)
    return frames


def decode_trle(trle: tuple[list[list[int]], list[list[int]], list[list[int]]]) -> list[SignedFrame]:
    # it has to reconstruct the pixel count fron the amount given
    y_frames, cb_frames, cr_frames = trle

    frames = []
    y_colors = decode_single_trle_color(y_frames)
    cb_colors = decode_single_trle_color(cb_frames)
    cr_colors = decode_single_trle_color(cr_frames)
    for frame_index in range(len(y_colors)):
        y_color = y_colors[frame_index]
        cb_color = cb_colors[frame_index]
        cr_color = cr_colors[frame_index]
        frames.append(SignedFrame(y=y_color, cb=cb_color, cr=cr_color))
    return frames


def interpolate_frames(colors: list[list[int]]) -> list[int]:
    interpolated_monochrom_frames = []
    for frame_index in tqdm(range(1, len(colors)), file=sys.stdout):
        last_colors = colors[frame_index - 1]
        current_colors = colors[frame_index]
        interpolated_colors = []
        for pixel_index in range(len(current_colors)):
            current_pixel = current_colors[pixel_index]
            last_pixel = last_colors[pixel_index]
            pixel_interpolation = (current_pixel + last_pixel) // 2
            interpolated_colors.append(pixel_interpolation)
        interpolated_monochrom_frames.append(interpolated_colors)
    return interpolated_monochrom_frames


def print_metadata(metadata: Y4MMetadata, frame: Frame) -> None:
    print("width: " + str(metadata.width))
    print("height: " + str(metadata.height))
    print("amount pixels: " + str(metadata.width * metadata.height))
    print("fps: " + str(metadata.fps))
    print("interlacingt: " + str(metadata.interlacing))
    print("aspect_ratio: " + str(metadata.aspect_ratio))
    print("chroma: " + str(metadata.chroma))
    print("y pixel per frame: " + str(len(frame.y)))
    print("cb pixel per frame: " + str(len(frame.cb)))
    print("cr pixel per frame: " + str(len(frame.cr)))


def display_frame(metadata: Y4MMetadata, frame: Frame) -> None:
    y_image = Image.frombytes("L", (int(metadata.width), int(metadata.height)), frame.y)
    # fewer chroma values because of 4:2:0
    cb_image = Image.frombytes("L", (metadata.width // 2, metadata.height // 2),
                               frame.cb)  # TODO: make this work with only len(cb) and aspect ratio
    cr_image = Image.frombytes("L", (metadata.width // 2, metadata.height // 2), frame.cr)

    # rescale chroma values to full resolution
    cb_image = cb_image.resize((metadata.width, metadata.height), Image.Resampling.NEAREST)
    cr_image = cr_image.resize((metadata.width, metadata.height), Image.Resampling.NEAREST)

    image = Image.merge("YCbCr", (y_image, cb_image, cr_image))
    image.show()


class BitWriter:
    """Collects individual bits (given as '0'/'1' strings) and packs them into
    full bytes. Needed because Huffman codes and quantized values have
    variable/non-byte-aligned bit lengths, unlike append_u32 which always
    writes whole bytes."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.current_byte = 0
        self.bits_filled = 0

    def write_bits(self, bitstring: str) -> None:
        for bit in bitstring:
            self.current_byte = (self.current_byte << 1) | int(bit)
            self.bits_filled += 1
            if self.bits_filled == 8:
                self.buffer.append(self.current_byte)
                self.current_byte = 0
                self.bits_filled = 0

    def flush(self) -> bytes:
        # Pad the final, not-yet-full byte with zero bits so it can be written out.
        if self.bits_filled > 0:
            self.current_byte <<= (8 - self.bits_filled)
            self.buffer.append(self.current_byte)
            self.bits_filled = 0
        return bytes(self.buffer)


class BitReader:
    """Reads individual bits back out of a byte sequence, MSB first, matching
    the order BitWriter wrote them in."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.byte_index = 0
        self.bit_index = 0

    def read_bit(self) -> int:
        byte = self.data[self.byte_index]
        bit = (byte >> (7 - self.bit_index)) & 1
        self.bit_index += 1
        if self.bit_index == 8:
            self.bit_index = 0
            self.byte_index += 1
        return bit


def append_i32(buffer: bytearray, value: int) -> None:
    # Signed 32-bit little-endian, unlike append_u32: residual values can be negative.
    buffer.extend(struct.pack("<i", value))


def read_i32(reader: ByteReader) -> int:
    return struct.unpack("<i", reader.read_bytes(4))[0]


# ---- Huffman tree construction ----
# Huffman coding assigns short bit-codes to frequent values and long bit-codes
# to rare ones, so the total number of bits needed to store a stream of
# values shrinks whenever the value distribution is skewed (as it is for our
# residuals, which cluster tightly around zero).

class HuffmanNode:
    def __init__(self, value: int | None = None, left: HuffmanNode | None = None,
                 right: HuffmanNode | None = None) -> None:
        self.value = value
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


def build_frequency_table(values: list[int]) -> dict[int, int]:
    """Counts how often each distinct value occurs in the input list."""
    frequency: dict[int, int] = {}
    for value in values:
        frequency[value] = frequency.get(value, 0) + 1
    return frequency


def build_huffman_tree(frequency: dict[int, int]) -> HuffmanNode:
    """Builds the Huffman tree bottom-up: repeatedly merges the two least
    frequent nodes into a new parent node until only the root remains. Values
    merged early end up deep in the tree, which is what makes rare values get
    long codes and frequent values get short codes."""
    nodes = [(freq, HuffmanNode(value=value)) for value, freq in frequency.items()]

    if len(nodes) == 1:
        return nodes[0][1]

    while len(nodes) > 1:
        nodes.sort(key=lambda item: item[0])
        freq_a, node_a = nodes.pop(0)
        freq_b, node_b = nodes.pop(0)
        merged = HuffmanNode(left=node_a, right=node_b)
        nodes.append((freq_a + freq_b, merged))

    return nodes[0][1]


def build_code_table(tree: HuffmanNode) -> dict[int, str]:
    """Walks the tree to read off each value's bit-code: '0' for every left
    turn, '1' for every right turn."""
    codes: dict[int, str] = {}

    def walk(node: HuffmanNode, path: str) -> None:
        if node.is_leaf:
            codes[node.value] = path or "0"
            return
        walk(node.left, path + "0")
        walk(node.right, path + "1")

    walk(tree, "")
    return codes


# ---- Packing / unpacking the code table itself ----
# The Huffman code table is not fixed in advance; it depends on the actual
# residual values in this video. The decoder therefore has no way to rebuild
# it on its own, so it has to be written into the bitstream alongside the
# compressed data.

def pack_huffman_table(buffer: bytearray, codes: dict[int, str]) -> None:
    append_u32(buffer, len(codes))
    for value, bitstring in codes.items():
        append_i32(buffer, value)
        buffer.append(len(bitstring))
        # Each table entry is byte-aligned on its own for simplicity; the
        # table is tiny compared to the frame data, so the few wasted
        # padding bits per entry don't matter.
        table_writer = BitWriter()
        table_writer.write_bits(bitstring)
        buffer.extend(table_writer.flush())


def unpack_huffman_table(reader: ByteReader) -> dict[str, int]:
    entry_count = reader.read_u32()
    reversed_codes: dict[str, int] = {}

    for _ in range(entry_count):
        value = read_i32(reader)
        code_length = reader.read_bytes(1)[0]
        byte_length = (code_length + 7) // 8
        packed = reader.read_bytes(byte_length)

        bitstring = ""
        for byte in packed:
            bitstring += format(byte, "08b")
        bitstring = bitstring[:code_length]  # drop the padding bits added by flush()

        reversed_codes[bitstring] = value  # inverted: bitstring -> value, needed for decoding

    return reversed_codes


# ---- Encoding / decoding a flat list of values with a code table ----

def huffman_encode_values(values: list[int], codes: dict[int, str]) -> bytes:
    writer = BitWriter()
    for value in tqdm(values, desc="huffman encoding", file=sys.stdout):
        writer.write_bits(codes[value])
    return writer.flush()


def huffman_decode_values(encoded_data: bytes, reversed_codes: dict[str, int], value_count: int) -> list[int]:
    # Huffman codes are prefix-free, so reading bit by bit and checking after
    # every bit whether the accumulated path is a known code is unambiguous.
    reader = BitReader(encoded_data)
    values: list[int] = []
    current_path = ""

    progress = tqdm(total=value_count, desc="huffman decoding", file=sys.stdout)
    while len(values) < value_count:
        current_path += str(reader.read_bit())
        if current_path in reversed_codes:
            values.append(reversed_codes[current_path])
            current_path = ""
            progress.update(1)
    progress.close()

    return values


def quantize_color(value: int, levels: int = 64) -> int:
    """Lossy spatial compression: maps an 8-bit color value (0-255) onto a
    smaller number of quantization levels by dividing it into fixed-size
    buckets. Fewer distinct values means the bitstream needs fewer bits per
    pixel later on, at the cost of losing fine color detail."""
    step = 256 // levels  # bucket width, e.g. 4 for 64 levels
    quantized = value // step
    return min(quantized, levels - 1)  # guard against the top bucket overflowing


def dequantize_color(quantized: int, levels: int = 64) -> int:
    """Reverses quantize_color as far as possible. The exact original value
    inside a bucket is lost, so we approximate it with the bucket's midpoint,
    which minimizes the average rounding error compared to always returning
    the bucket's lower edge."""
    step = 256 // levels
    value = quantized * step + step // 2
    return min(value, 255)


def quantize_plane(plane: bytes, levels: int = 64) -> bytes:
    """Applies quantize_color to every pixel of a single plane (Y, Cb or Cr)."""
    return bytes(quantize_color(v, levels) for v in plane)


def dequantize_plane(plane: bytes, levels: int = 64) -> bytes:
    """Applies dequantize_color to every pixel of a single plane."""
    return bytes(dequantize_color(v, levels) for v in plane)


def quantize_frame(frame: Frame, levels: int = 64) -> Frame:
    """Quantizes all three planes of a frame."""
    return Frame(
        y=quantize_plane(frame.y, levels),
        cb=quantize_plane(frame.cb, levels),
        cr=quantize_plane(frame.cr, levels),
    )


def dequantize_frame(frame: Frame, levels: int = 64) -> Frame:
    """Dequantizes all three planes of a frame."""
    return Frame(
        y=dequantize_plane(frame.y, levels),
        cb=dequantize_plane(frame.cb, levels),
        cr=dequantize_plane(frame.cr, levels),
    )


def lossy_temporal_reduce(frames: list[Frame]) -> list[Frame]:
    """Lossy temporal compression: keeps only every second frame."""
    return [frames[i] for i in range(0, len(frames), 2)]


def lossy_temporal_interpolate(reduced_frames: list[Frame]) -> list[Frame]:
    """Reconstructs the dropped frames by averaging each kept frame with the
    next one, filling the gaps back in so the video regains its original
    frame count (at reduced motion quality)."""
    y_colors = [f.y for f in reduced_frames]
    cb_colors = [f.cb for f in reduced_frames]
    cr_colors = [f.cr for f in reduced_frames]

    y_interp = interpolate_frames(y_colors)
    cb_interp = interpolate_frames(cb_colors)
    cr_interp = interpolate_frames(cr_colors)

    interpolated_frames = []
    for i in range(len(reduced_frames)):
        interpolated_frames.append(reduced_frames[i])
        if i < len(y_interp):
            interpolated_frames.append(Frame(
                y=bytes(y_interp[i]), cb=bytes(cb_interp[i]), cr=bytes(cr_interp[i])
            ))
    interpolated_frames.append(reduced_frames[-1])
    return interpolated_frames


# ============================================================================
# Student bitstream
# Students edit: yes | purpose: define your own binary format.
# ============================================================================

def pack_lossless_bitstream(metadata: Y4MMetadata, signed_frames: list[SignedFrame]) -> bytes:
    """Packs residual frames (spatial + temporal prediction already applied)
    into a Huffman-compressed container.

    Layout:
      "LS01"                       4 bytes, magic / format version
      metadata                     width, height, fps, interlacing, aspect, chroma
      huffman table                shared code table for every residual value in the video
      frame_count                  u32
      per frame: y_len, cb_len, cr_len   3x u32, so the decoder knows where
                                          each frames planes end inside the
                                          single flat value stream below
      encoded_length                u32
      encoded_data                  the Huffman-coded bits for ALL residuals
                                     of the whole video
    """
    output = bytearray()
    output.extend(b"LS01")
    pack_metadata(output, metadata)

    # Flatten every residual across every frame/plane so a single, shared
    # code table can be built for the whole video (one table is simpler and
    # cheaper to store than one table per frame).
    print("packing lossless", flush=True)
    all_values: list[int] = []
    for frame in tqdm(signed_frames, desc="collecting residuals", file=sys.stdout):
        all_values.extend(frame.y)
        all_values.extend(frame.cb)
        all_values.extend(frame.cr)

    frequency = build_frequency_table(all_values)
    tree = build_huffman_tree(frequency)
    codes = build_code_table(tree)
    pack_huffman_table(output, codes)

    # Store how long each plane is so the decoder can later cut the single
    # decoded value stream back into the correct per-frame/per-plane pieces.
    append_u32(output, len(signed_frames))
    for frame in tqdm(signed_frames, desc="writing frame lengths", file=sys.stdout):
        append_u32(output, len(frame.y))
        append_u32(output, len(frame.cb))
        append_u32(output, len(frame.cr))

    encoded_data = huffman_encode_values(all_values, codes)
    append_u32(output, len(encoded_data))
    output.extend(encoded_data)

    return bytes(output)


def unpack_lossless_bitstream(data: bytes) -> tuple[Y4MMetadata, list[SignedFrame]]:
    """Reverses pack_lossless_bitstream: reads the container back into
    residual frames (decode_lossless then still needs to undo temporal and
    spatial prediction to turn these into real pixel data"""
    reader = ByteReader(data)

    magic = reader.read_bytes(4)
    if magic != b"LS01":
        raise ValueError("Invalid lossless container")

    metadata = unpack_metadata(reader)
    reversed_codes = unpack_huffman_table(reader)

    frame_count = reader.read_u32()
    plane_lengths: list[tuple[int, int, int]] = []
    print("unpacking lossless", flush=True)
    for _ in tqdm(range(frame_count), desc="reading frame lengths", file=sys.stdout):
        y_len = reader.read_u32()
        cb_len = reader.read_u32()
        cr_len = reader.read_u32()
        plane_lengths.append((y_len, cb_len, cr_len))

    encoded_length = reader.read_u32()
    encoded_data = reader.read_bytes(encoded_length)

    total_values = sum(sum(lengths) for lengths in plane_lengths)
    all_values = huffman_decode_values(encoded_data, reversed_codes, total_values)

    # Cut the single flat value stream back into per-frame/per-plane chunks,
    # using the lengths stored above, in the same order they were written.
    signed_frames: list[SignedFrame] = []
    position = 0
    for y_len, cb_len, cr_len in tqdm(plane_lengths, desc="rebuilding frames", file=sys.stdout):
        y = all_values[position:position + y_len]
        position += y_len
        cb = all_values[position:position + cb_len]
        position += cb_len
        cr = all_values[position:position + cr_len]
        position += cr_len
        signed_frames.append(SignedFrame(y=y, cb=cb, cr=cr))

    return metadata, signed_frames


def pack_lossy_bitstream(metadata: Y4MMetadata, frames: list[Frame], levels: int = 64) -> bytes:
    """Packs already-quantized frames into a bit-packed container. Since
    every quantized value is guaranteed to be in [0, levels), each value only
    needs as many bits as required to represent (levels - 1), instead of a
    full byte per pixel

    Layout:
      "LY01"                        4 bytes, magic / format version
      metadata
      frame_count                   u32
      levels                        u32, quantization level count (needed to know bits_per_value)
      per frame: y_len, cb_len, cr_len   3x u32
      encoded_length                u32
      encoded_data                  all pixel values, bit-packed with
                                     bits_per_value bits each, back to back
    """
    output = bytearray()
    output.extend(b"LY01")
    pack_metadata(output, metadata)
    append_u32(output, len(frames))
    append_u32(output, levels)

    for frame in frames:
        append_u32(output, len(frame.y))
        append_u32(output, len(frame.cb))
        append_u32(output, len(frame.cr))

    bits_per_value = (levels - 1).bit_length()  # e.g. levels=64 -> 6 bits per value instead of 8

    print("packing lossy", flush=True)
    writer = BitWriter()
    for frame in tqdm(frames, desc="bit-packing frames", file=sys.stdout):
        for plane in (frame.y, frame.cb, frame.cr):
            for value in plane:
                writer.write_bits(format(value, f"0{bits_per_value}b"))
    encoded_data = writer.flush()

    append_u32(output, len(encoded_data))
    output.extend(encoded_data)
    return bytes(output)


def unpack_lossy_bitstream(data: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    """Reverses pack_lossy_bitstream: reads the bit-packed quantized values
    back out (decode_lossy then still needs to dequantize and interpolate
    them into full-size pixel frames)."""
    reader = ByteReader(data)
    if reader.read_bytes(4) != b"LY02":
        raise ValueError("Invalid lossy container")

    metadata = unpack_metadata(reader)
    frame_count = reader.read_u32()
    levels = reader.read_u32()

    plane_lengths = [(reader.read_u32(), reader.read_u32(), reader.read_u32()) for _ in range(frame_count)]

    encoded_length = reader.read_u32()
    encoded_data = reader.read_bytes(encoded_length)

    bits_per_value = (levels - 1).bit_length()
    bit_reader = BitReader(encoded_data)

    def read_value() -> int:
        bits = "".join(str(bit_reader.read_bit()) for _ in range(bits_per_value))
        return int(bits, 2)

    frames = []
    print("unpacking lossy", flush=True)
    for y_len, cb_len, cr_len in tqdm(plane_lengths, desc="bit-unpacking frames", file=sys.stdout):
        y = bytes(read_value() for _ in range(y_len))
        cb = bytes(read_value() for _ in range(cb_len))
        cr = bytes(read_value() for _ in range(cr_len))
        frames.append(Frame(y=y, cb=cb, cr=cr))

    return metadata, frames


# ============================================================================
# Student codec
# Students edit: yes | purpose: implement lossless and lossy coding.
# ============================================================================

def encode_lossless(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    print("encoding lossless")
    starting_color = 128

    # Step 1: spatial prediction. Each pixel is replaced by the difference to
    # the previous pixel in the same plane, so the resulting values cluster
    # tightly around zero wherever the image is locally smooth.
    print("spatial compression", flush=True)
    predictive_frames: list[SignedFrame] = []
    for frame in tqdm(frames, file=sys.stdout):
        predictive_frame_y = encode_predictive_compression(frame.y, starting_color)
        predictive_frame_cb = encode_predictive_compression(frame.cb, starting_color)
        predictive_frame_cr = encode_predictive_compression(frame.cr, starting_color)
        predictive_frames.append(SignedFrame(y=predictive_frame_y, cb=predictive_frame_cb, cr=predictive_frame_cr))

    # Step 2: temporal prediction. Each spatially-predicted frame is replaced
    # by its difference to the previous spatially-predicted frame, so areas
    # that don't change between frames collapse to (mostly) zero.
    print("temporal compression", flush=True)
    signed_frames = temporal_predictive_compression(predictive_frames)

    # Step 3: serialize the resulting residuals into the bitstream (Huffman
    # coding happens inside pack_lossless_bitstream).
    return pack_lossless_bitstream(metadata, signed_frames)


def decode_lossless(bitstream: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    # Step 1: parse the container and Huffman-decode the residuals back out.
    metadata, signed_frames = unpack_lossless_bitstream(bitstream)

    # Step 2: undo the temporal prediction, oldest frame first, since every
    # later frame's real value depends on the previous frame already being
    # reconstructed.
    print("temporal decompression", flush=True)
    spatial_encoded_frames = decode_temporal_compression(signed_frames)

    # Step 3: undo the spatial prediction within each frame, turning the
    # signed residual lists back into normal 0-255 pixel bytes.
    print("spatial decompression", flush=True)
    frames: list[Frame] = []
    for frame in tqdm(spatial_encoded_frames, file=sys.stdout):
        y_frame = bytes(decode_predictive_compression(frame.y))
        cb_frame = bytes(decode_predictive_compression(frame.cb))
        cr_frame = bytes(decode_predictive_compression(frame.cr))
        frames.append(Frame(y=y_frame, cb=cb_frame, cr=cr_frame))

    return metadata, frames


def encode_lossy(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    print("encoding lossy")

    # Step 1: temporal compression by dropping every second frame. The
    # dropped frames are deliberately NOT refilled here - that only happens
    # after decoding (see decode_lossy). This way the packed bitstream really
    # only contains half as many frames, instead of throwing frames away and
    # immediately reconstructing them again before packing.
    print("temporal compression", flush=True)
    reduced_frames = lossy_temporal_reduce(frames)

    # Step 2: spatial compression by reducing every pixel from 256 possible
    # values down to `levels` values (quantization).
    print("spatial compression (256 -> 64 colors)", flush=True)
    quantized_frames = [quantize_frame(f, levels=64) for f in tqdm(reduced_frames, file=sys.stdout)]

    # Step 3: bit-pack the quantized values into the bitstream.
    return pack_lossy_bitstream(metadata, quantized_frames)


def decode_lossy(bitstream: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    # Step 1: parse the container and unpack the bit-packed quantized values.
    metadata, quantized_frames = unpack_lossy_bitstream(bitstream)

    # Step 2: undo the quantization. The exact original color is lost, so
    # each value is mapped back to the midpoint of its quantization bucket.
    print("spatial decompression (64 -> ~256 colors)", flush=True)
    dequantized_frames = [dequantize_frame(f, levels=64) for f in quantized_frames]

    # Step 3: undo the temporal compression by refilling the frames that were
    # dropped during encoding, averaging neighboring frames to approximate
    # them. This restores the original frame count. Note: the very last
    # frame has no following neighbor to interpolate from, so it is simply
    # duplicated as a rough stand-in instead.
    print("temporal decompression", flush=True)
    frames = lossy_temporal_interpolate(dequantized_frames)

    return metadata, frames


# ============================================================================
# Pipeline
# Students edit: no | purpose: run both encode/decode pipelines automatically.
# ============================================================================

def run_lossless_pipeline(metadata: Y4MMetadata, frames: list[Frame]) -> None:
    bitstream = encode_lossless(metadata, frames)
    write_bitstream(LOSSLESS_BIN_FILE, bitstream)

    decoded_metadata, decoded_frames = decode_lossless(read_bitstream(LOSSLESS_BIN_FILE))
    write_y4m(LOSSLESS_Y4M_FILE, decoded_metadata, decoded_frames)


def run_lossy_pipeline(metadata: Y4MMetadata, frames: list[Frame]) -> None:
    bitstream = encode_lossy(metadata, frames)
    write_bitstream(LOSSY_BIN_FILE, bitstream)

    decoded_metadata, decoded_frames = decode_lossy(read_bitstream(LOSSY_BIN_FILE))
    write_y4m(LOSSY_Y4M_FILE, decoded_metadata, decoded_frames)


# ============================================================================
# Entry point
# Students edit: no | purpose: execute the full workflow.
# ============================================================================

def main() -> None:
    ensure_output_directory()

    metadata, frames = read_y4m(SOURCE_FILE)

    run_lossy_pipeline(metadata, frames)
    run_lossless_pipeline(metadata, frames)

    print("Finished.")
    print(f"Created: {LOSSLESS_BIN_FILE}")
    print(f"Created: {LOSSLESS_Y4M_FILE}")
    print(f"Created: {LOSSY_BIN_FILE}")
    print(f"Created: {LOSSY_Y4M_FILE}")


if __name__ == "__main__":
    main()