from __future__ import annotations

import sys
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
    print("encoding lossless")
    # ---encoding spatial compression---
    starting_color = 128
    predictive_frames = []
    # predictive_frames format: list of SignedFrame: SignedFrame has lists for y, cb, cr each habe list:
    # starting_value difference_0 difference_1 difference_2 etc.
    print("spatial compression", flush=True)
    for frame in tqdm(frames, file=sys.stdout):
        predictive_frame_y = encode_predictive_compression(frame.y, starting_color)
        predictive_frame_cb = encode_predictive_compression(frame.cb, starting_color)
        predictive_frame_cr = encode_predictive_compression(frame.cr, starting_color)
        predictive_frames.append(SignedFrame(y=predictive_frame_y, cb=predictive_frame_cb, cr=predictive_frame_cr))

    # ---encoding temporal compression---
    print("temporal compression", flush=True)
    temporal_and_spatial_encoded_frames = temporal_predictive_compression(predictive_frames)
    # for i in range(100):
    #    print(predictive_frames[1].y[i])

    print("decoding lossless")
    # ---decoding temporal compression---
    print("temporal decompression", flush=True)
    spatial_encoded_frames = decode_temporal_compression(temporal_and_spatial_encoded_frames)

    # ---decoding spatial compression---
    print("spatial decompression", flush=True)
    frames_2 = []
    for frame in tqdm(spatial_encoded_frames, file=sys.stdout):
        y_frame = bytes(decode_predictive_compression(frame.y))
        cb_frame = bytes(decode_predictive_compression(frame.cb))
        cr_frame = bytes(decode_predictive_compression(frame.cr))
        frames_2.append(Frame(y=y_frame, cb=cb_frame, cr=cr_frame))

    display_frame(metadata, frames_2[100])

    return pack_lossless_bitstream(metadata, frames_2)


def decode_lossless(bitstream: bytes) -> tuple[Y4MMetadata, list[Frame]]:
    return unpack_lossless_bitstream(bitstream)


def encode_lossy(metadata: Y4MMetadata, frames: list[Frame]) -> bytes:
    print("encoding lossy")
    # ---encoding temporal compression---
    print("temporal compression", flush=True)
    reduced_frames = []
    for frame_index in tqdm(range(0, len(frames), 2), file=sys.stdout):
        reduced_frames.append(frames[frame_index])

    print("decoding lossy")
    print("temporal decompression", flush=True)
    # ---decoding temporal compression---
    # generating frames
    y_colors = []
    cb_colors = []
    cr_colors = []
    for frame in reduced_frames:
        y_colors.append(frame.y)
        cb_colors.append(frame.cb)
        cr_colors.append(frame.cr)

    y_colors_interpolated = interpolate_frames(y_colors)
    cb_colors_interpolated = interpolate_frames(cb_colors)
    cr_colors_interpolated = interpolate_frames(cr_colors)

    interpolated_frames = []
    for i in tqdm(range(len(reduced_frames)), file=sys.stdout):
        interpolated_frames.append(reduced_frames[i])
        if i < len(y_colors_interpolated):
            frame = Frame(y=bytes(y_colors_interpolated[i]), cb=bytes(cb_colors_interpolated[i]),
                          cr=bytes(cr_colors_interpolated[i]))
            interpolated_frames.append(frame)

    # there may be one less interpolated frame so to get to the full frame count one extra frame needs to be added.
    interpolated_frames.append(reduced_frames[-1])

    return pack_lossy_bitstream(metadata, interpolated_frames)


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
