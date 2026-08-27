from __future__ import annotations

from asyncio.windows_events import NULL
from dataclasses import dataclass
from pathlib import Path
import struct
import warnings

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

def rle_efficiency_test(metadata: Y4MMetadata, frames: list[Frame]) -> None:
    print_metadata(metadata, frames[0])
    for i in range(20):
        print(len(run_length_encoding(metadata, frames[i].y)))
        print(len(run_length_encoding(metadata, frames[i].cb)))
        print(len(run_length_encoding(metadata, frames[i].cr)))


# does not work here, generates larger sizes
def run_length_encoding(metadata: Y4MMetadata, colors: bytes) -> list[int]:
    # Run-Length Encoding (RLE)
    # Encodes how often a color repeats: amount_of_repetition color_value
    last_color = colors[0]
    repetition = 1
    rle_encoding = []
    for color in colors:
        if color == last_color:
            repetition += 1
        else:
            rle_encoding.append(repetition)
            rle_encoding.append(last_color)
            repetition = 1
            last_color = color
    return rle_encoding


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


def show_frame(metadata: Y4MMetadata, frame: Frame) -> None:
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


# ============================================================================
# Student bitstream
# Students edit: yes | purpose: define your own binary format.
# ============================================================================

def pack_lossless_bitstream(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    """Pack custom lossless payload into a container."""
    warnings.warn(
        "Fallback lossless bitstream in use. Replace before submission.",
        stacklevel=2,
    )

    output = bytearray()
    output.extend(b"LS00")
    pack_metadata(output, metadata)
    append_u32(output, len(frames))

    for frame in frames:
        for plane in (frame.y, frame.cb, frame.cr):
            append_u32(output, len(plane))
            output.extend(plane)

    return bytes(output)


def unpack_lossless_bitstream(data: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    """Unpack custom lossless container."""
    warnings.warn(
        "Fallback lossless parser in use. Replace before submission.",
        stacklevel=2,
    )

    reader = ByteReader(data)

    magic = reader.read_bytes(4)
    if magic != b"LS00":
        raise ValueError("Invalid fallback lossless container")

    metadata = unpack_metadata(reader)
    frame_count = reader.read_u32()

    frames: list[Frame] = []
    for _ in range(frame_count):
        y = reader.read_bytes(reader.read_u32())
        cb = reader.read_bytes(reader.read_u32())
        cr = reader.read_bytes(reader.read_u32())
        frames.append(Frame(y=y, cb=cb, cr=cr))

    return metadata, frames


def pack_lossy_bitstream(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    """Pack custom lossy payload into a container."""
    warnings.warn(
        "Fallback lossy bitstream in use. Replace before submission.",
        stacklevel=2,
    )

    output = bytearray()
    output.extend(b"LY00")
    pack_metadata(output, metadata)
    append_u32(output, len(frames))

    for frame in frames:
        for plane in (frame.y, frame.cb, frame.cr):
            append_u32(output, len(plane))
            output.extend(plane)

    return bytes(output)


def unpack_lossy_bitstream(data: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    """Unpack custom lossy container."""
    warnings.warn(
        "Fallback lossy parser in use. Replace before submission.",
        stacklevel=2,
    )

    reader = ByteReader(data)

    magic = reader.read_bytes(4)
    if magic != b"LY00":
        raise ValueError("Invalid fallback lossy container")

    metadata = unpack_metadata(reader)
    frame_count = reader.read_u32()

    frames: list[Frame] = []
    for _ in range(frame_count):
        y = reader.read_bytes(reader.read_u32())
        cb = reader.read_bytes(reader.read_u32())
        cr = reader.read_bytes(reader.read_u32())
        frames.append(Frame(y=y, cb=cb, cr=cr))

    return metadata, frames


# ============================================================================
# Student codec
# Students edit: yes | purpose: implement lossless and lossy coding.
# ============================================================================

def encode_lossless(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    metadata.width
    metadata.height
    # spatial compression
    # in a section, save only one color or breightness value if they all match
    # a section is defined as 3x3 in a grid pattern

    rle_efficiency_test(metadata, frames)

    # temporal compression

    """Implement lossless coding here."""
    return pack_lossless_bitstream(metadata, frames)


def decode_lossless(bitstream: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    """Implement lossless decoding here."""
    return unpack_lossless_bitstream(bitstream)


def encode_lossy(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    """Implement lossy coding here."""
    return pack_lossy_bitstream(metadata, frames)


def decode_lossy(bitstream: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    """Implement lossy decoding here."""
    return unpack_lossy_bitstream(bitstream)


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

    run_lossless_pipeline(metadata, frames)
    run_lossy_pipeline(metadata, frames)

    print("Finished.")
    print(f"Created: {LOSSLESS_BIN_FILE}")
    print(f"Created: {LOSSLESS_Y4M_FILE}")
    print(f"Created: {LOSSY_BIN_FILE}")
    print(f"Created: {LOSSY_Y4M_FILE}")


if __name__ == "__main__":
    main()
