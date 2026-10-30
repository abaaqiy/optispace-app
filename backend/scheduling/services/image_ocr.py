"""Bounded local OCR with table geometry and a pinned PP-OCRv5 recognizer."""

import csv
import io
import os
from pathlib import Path
import math
import re
import subprocess
import tempfile
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageOps

from .timetable_import import ImportProblem

MAX_PIXELS = 20_000_000
WORK_PIXELS = 7_000_000
OCR_SECONDS = 65
deadline = ContextVar("image_ocr_deadline", default=None)
cv2.setNumThreads(1)


@dataclass
class Cell:
    text: str
    box: tuple
    confidence: float | None = None
    words: list = field(default_factory=list)
    note: str = ""
    has_content: bool = False


def run_ocr(image, *, psm=6):
    executable = os.environ.get("TESSERACT_CMD", "tesseract")
    remaining = (deadline.get() or (time.monotonic() + 25)) - time.monotonic()
    if remaining <= 0:
        raise ImportProblem(
            "Reading this image took too long. Upload one smaller, clearer timetable section with its headings."
        )
    # Bound the independent reader's memory even on very tall heading atlases.
    scale = min(1, (2_000_000 / (image.width * image.height)) ** 0.5)
    if scale < 1:
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        )
    with tempfile.TemporaryDirectory(prefix="optispace-ocr-") as directory:
        path = Path(directory) / "cells.png"
        image.save(path)
        command = [
            executable,
            str(path),
            "stdout",
            "-l",
            "eng",
            "--oem",
            "1",
            "--psm",
            str(psm),
            "-c",
            "tessedit_create_tsv=1",
            "-c",
            "load_system_dawg=0",
            "-c",
            "load_freq_dawg=0",
        ]
        model_dir = os.environ.get("OPTISPACE_OCR_DATA")
        if model_dir:
            command += ["--tessdata-dir", model_dir]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=True,
                timeout=min(25, remaining),
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
        except FileNotFoundError as error:
            raise ImportProblem(
                "Image reading needs Tesseract OCR. See the image-import setup guide."
            ) from error
        except subprocess.TimeoutExpired as error:
            raise ImportProblem(
                "Reading this image took too long. Use a clearer or smaller image with the day/time headings visible."
            ) from error
        except subprocess.CalledProcessError as error:
            raise ImportProblem(
                "The image reader could not start. Check its English model installation."
            ) from error
    words = []
    for row in csv.DictReader(
        io.StringIO(result.stdout.decode("utf-8", errors="replace")),
        delimiter="\t",
        quoting=csv.QUOTE_NONE,
    ):
        if row.get("text", "").strip() and float(row["conf"]) >= 0:
            x, y, w, h = (int(row[key]) for key in ("left", "top", "width", "height"))
            words.append(
                {
                    "text": row["text"],
                    "x0": x / scale,
                    "top": y / scale,
                    "x1": (x + w) / scale,
                    "bottom": (y + h) / scale,
                    "confidence": float(row["conf"]),
                }
            )
    return words


def text_words(words):
    lines = []
    for word in sorted(
        words, key=lambda word: ((word["top"] + word["bottom"]) / 2, word["x0"])
    ):
        cy = (word["top"] + word["bottom"]) / 2
        height = word["bottom"] - word["top"]
        found = next(
            (
                line
                for line in reversed(lines[-2:])
                if abs(line[0] - cy) < max(3, height * 0.5)
            ),
            None,
        )
        if found is None:
            lines.append((cy, [word]))
        else:
            found[1].append(word)
    return "\n".join(
        " ".join(word["text"] for word in sorted(line, key=lambda word: word["x0"]))
        for _, line in lines
    )


def positions(values, threshold, gap=7):
    groups = []
    for value in np.flatnonzero(values >= threshold):
        if groups and value - groups[-1][-1] <= gap:
            groups[-1].append(int(value))
        else:
            groups.append([int(value)])
    return [round(sum(group) / len(group)) for group in groups]


def prepare_image(image):
    if image.width * image.height > MAX_PIXELS:
        raise ImportProblem("Use an image of at most 20 megapixels.")
    scale = min(
        5, 3000 / max(image.size), (WORK_PIXELS / (image.width * image.height)) ** 0.5
    )
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    # Resize before EXIF/colour copies to avoid several full-size 20 MP buffers.
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        image = background.convert("RGB")
    else:
        image = image.convert("RGB")
    grey = np.asarray(image.convert("L"))
    edges = cv2.Canny(grey, 60, 160)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 1800, 100, minLineLength=image.width // 4, maxLineGap=20
    )
    angles = []
    for x0, y0, x1, y1 in lines[:, 0] if lines is not None else []:
        angle = float(np.degrees(np.arctan2(y1 - y0, x1 - x0)))
        if abs(angle) < 7:
            angles.append(angle)
    angle = float(np.median(angles)) if angles else 0
    if 0.12 < abs(angle) < 7:
        image = image.rotate(
            angle, Image.Resampling.BICUBIC, expand=False, fillcolor="white"
        )
    return image


@lru_cache(maxsize=1)
def recognition_model():
    """Load only the small English recognizer; no downloads during requests."""
    model = Path(
        os.environ.get(
            "OPTISPACE_IMAGE_MODEL",
            Path(__file__).resolve().parents[1] / "ocr_models/english.onnx",
        )
    )
    if not model.is_file():
        raise ImportProblem(
            "The image recognition model is not installed. Run scripts/install-image-model.py before starting the server."
        )
    import onnxruntime as ort

    ort.disable_telemetry_events()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.log_severity_level = 3
    session = ort.InferenceSession(
        str(model), sess_options=options, providers=["CPUExecutionProvider"]
    )
    characters = (
        [""]
        + session.get_modelmeta().custom_metadata_map["character"].splitlines()
        + [" "]
    )
    return session, characters


def recognise_line(crop):
    session, characters = recognition_model()
    if deadline.get() is not None and time.monotonic() > deadline.get():
        raise ImportProblem(
            "Reading this image took too long. Upload one smaller section with its day/time headings."
        )
    h, w = crop.shape[:2]
    width = min(1600, max(32, math.ceil(48 * w / h)))
    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    value = (
        cv2.resize(crop, (width, 48)).astype(np.float32).transpose(2, 0, 1) / 127.5 - 1
    )
    predictions = session.run(None, {session.get_inputs()[0].name: value[None]})[0][0]
    indices, scores = predictions.argmax(axis=1), predictions.max(axis=1)
    selected = indices != 0
    selected[1:] &= indices[1:] != indices[:-1]
    text = "".join(characters[index] for index in indices[selected]).strip()
    confidence = float(np.mean(scores[selected])) * 100 if selected.any() else 0
    return text, confidence


def line_regions(crop):
    """Split text using ink rows, then tightly crop each line for recognition."""
    grey = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if crop.ndim == 3 else crop
    binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    height, width = binary.shape
    _, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    for x, y, w, h, area in stats[1:]:
        if w > width * 0.8 and h < 6 or h > height * 0.85 and w < 6:
            binary[y : y + h, x : x + w] = 0
    groups = []
    for y in np.flatnonzero((binary > 0).sum(axis=1) > max(1, width * 0.008)):
        if groups and y - groups[-1][-1] <= 3:
            groups[-1].append(int(y))
        else:
            groups.append([int(y)])
    for group in groups:
        top, bottom = group[0], group[-1] + 1
        if bottom - top < 4:
            continue
        xs = np.flatnonzero((binary[top:bottom] > 0).sum(axis=0) > 0)
        if not len(xs):
            continue
        left, right = int(xs[0]), int(xs[-1]) + 1
        if right - left < 4 or np.count_nonzero(binary[top:bottom, left:right]) < 10:
            continue
        box = (
            max(0, left - 3),
            max(0, top - 3),
            min(width, right + 3),
            min(height, bottom + 3),
        )
        yield grey[box[1] : box[3], box[0] : box[2]], box


def read_cells(cells, cleaned, rotated_cells):
    for cell in cells:
        x0, y0, x1, y1 = (round(value) for value in cell.box)
        crop = cleaned[y0 + 4 : y1 - 4, x0 + 4 : x1 - 4]
        if not crop.size:
            continue
        rotated = id(cell) in rotated_cells
        if rotated:
            crop = np.rot90(crop, k=3).copy()
        words = []
        for line, box in line_regions(crop):
            cell.has_content = True
            text, confidence = recognise_line(line)
            if not text or not any(char.isalnum() for char in text):
                continue
            if rotated:
                box = cell.box
            else:
                box = (
                    box[0] + x0 + 4,
                    box[1] + y0 + 4,
                    box[2] + x0 + 4,
                    box[3] + y0 + 4,
                )
            words.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "x0": box[0],
                    "top": box[1],
                    "x1": box[2],
                    "bottom": box[3],
                }
            )
        cell.words = words
        cell.text = "\n".join(word["text"] for word in words)
        cell.confidence = min((word["confidence"] for word in words), default=None)


def reread_headings(tables, cleaned, rotated_cells):
    """Two independent reads for weekday/time headings; do not guess missing ones."""
    from .document_extract import clock_range, day_value, heading_label

    selected = {}
    for table in tables:
        for row in table[:2]:
            for cell in row:
                selected[id(cell)] = cell
        for row in table:
            selected[id(row[0])] = row[0]
    pending = []
    top = 12
    for cell in selected.values():
        x0, y0, x1, y1 = (round(v) for v in cell.box)
        crop = cleaned[y0 + 4 : y1 - 4, x0 + 4 : x1 - 4]
        if not crop.size:
            continue
        if id(cell) in rotated_cells:
            crop = np.rot90(crop, k=3).copy()
        for line, box in line_regions(crop):
            if line.shape[1] > 1800 or top + line.shape[0] > 9000:
                continue
            pending.append((cell, line, top))
            top += line.shape[0] + 30
    if not pending:
        return
    atlas = Image.new(
        "L", (max(line.shape[1] for _, line, _ in pending) + 40, top), 255
    )
    for cell, line, top in pending:
        atlas.paste(Image.fromarray(line), (20, top))
    words = run_ocr(atlas, psm=6)
    by_cell = {}
    for cell, line, top in pending:
        selected_words = [
            word
            for word in words
            if top <= (word["top"] + word["bottom"]) / 2 < top + line.shape[0]
        ]
        by_cell.setdefault(id(cell), []).append(text_words(selected_words))
    for cell in selected.values():
        alternative = "\n".join(by_cell.get(id(cell), [])).strip()
        old = cell.text
        if not alternative or alternative == old:
            continue
        old_day, new_day = day_value(old), day_value(alternative)
        old_clock, new_clock = clock_range(old), clock_range(alternative)
        if new_day and not old_day or new_clock[0] and not old_clock[0]:
            cell.text = alternative
            cell.note = (
                "Heading recovered by a second reader; check it once for this group."
            )
        elif (
            old_day
            and new_day
            and old_day != new_day
            or old_clock[0]
            and new_clock[0]
            and old_clock != new_clock
        ):
            cell.text = ""
            cell.note = f"Readers disagree ({old} / {alternative}). Select the correct heading from the image."
        elif (
            heading_label(alternative)
            and not heading_label(old)
            and not old_day
            and not old_clock[0]
        ):
            cell.text = alternative


def image_tables(source):
    image = prepare_image(source)
    grey = np.asarray(image.convert("L"))
    dark = cv2.adaptiveThreshold(
        grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, 10
    )
    horizontal = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, image.width // 24), 1)),
    )
    vertical = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(28, image.height // 80))),
    )
    grid = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(
        cv2.dilate(grid, np.ones((5, 5), np.uint8)),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    boxes = sorted((cv2.boundingRect(c) for c in contours), key=lambda box: box[1])
    boxes = [
        box
        for box in boxes
        if box[2] > image.width * 0.45 and box[3] > image.height * 0.1
    ]
    background = cv2.GaussianBlur(grey, (0, 0), 20)
    cleaned = cv2.divide(grey, background, scale=255)
    tables, all_cells, notes, rotated_cells = [], [], [], set()
    for x, y, w, h in boxes[:6]:
        xs = [
            x + i
            for i in positions(
                (vertical[y : y + h, x : x + w] > 0).sum(axis=0), h * 0.28
            )
        ]
        ys = [
            y + i
            for i in positions(
                (horizontal[y : y + h, x : x + w] > 0).sum(axis=1), w * 0.22
            )
        ]
        if xs and x + w >= image.width - 5 and xs[-1] < image.width - 10:
            xs.append(image.width - 1)
            notes.append(
                "The table's right edge is cropped; check entries in the final column against a complete image."
            )
        if len(xs) < 3 or len(ys) < 3:
            continue
        if len(xs) > 32 or len(ys) > 160:
            raise ImportProblem(
                "This image contains too many cells. Upload one timetable section with its headings."
            )
        # Erase only detected table rules, never short strokes inside text glyphs.
        for xx in xs:
            mask = vertical[y : y + h, max(0, xx - 4) : xx + 5] > 0
            cleaned[y : y + h, max(0, xx - 4) : xx + 5][mask] = 255
        for yy in ys:
            mask = horizontal[max(0, yy - 4) : yy + 5, x : x + w] > 0
            cleaned[max(0, yy - 4) : yy + 5, x : x + w][mask] = 255
        nr, nc = len(ys) - 1, len(xs) - 1
        parent = list(range(nr * nc))

        def find(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def join(a, b):
            parent[find(b)] = find(a)

        for r in range(nr):
            for c in range(nc):
                x0, x1, y0, y1 = xs[c], xs[c + 1], ys[r], ys[r + 1]
                if r and c == 0:
                    stroke = horizontal[max(0, y0 - 4) : y0 + 5, x0 + 5 : x1 - 5]
                    if stroke.size and (stroke > 0).any(axis=0).mean() < 0.2:
                        join(r * nc + c, (r - 1) * nc + c)
                if c and r == 0:
                    stroke = vertical[y0 + 5 : y1 - 5, max(0, x0 - 4) : x0 + 5]
                    if stroke.size and (stroke > 0).any(axis=1).mean() < 0.2:
                        join(r * nc + c, r * nc + c - 1)
        members = {}
        for r in range(nr):
            for c in range(nc):
                members.setdefault(find(r * nc + c), []).append((r, c))
        cells = {}
        for key, indices in members.items():
            rr, cc = [i[0] for i in indices], [i[1] for i in indices]
            if len(indices) != (max(rr) - min(rr) + 1) * (max(cc) - min(cc) + 1):
                # Broken borders must not merge an L-shaped set of unrelated entries.
                for r, c in indices:
                    cells[(r, c)] = Cell("", (xs[c], ys[r], xs[c + 1], ys[r + 1]))
            else:
                cell = Cell(
                    "", (xs[min(cc)], ys[min(rr)], xs[max(cc) + 1], ys[max(rr) + 1])
                )
                for index in indices:
                    cells[index] = cell
        table = [[cells[(r, c)] for c in range(nc)] for r in range(nr)]
        for row in table:
            cell = row[0]
            if cell.box[3] - cell.box[1] > (cell.box[2] - cell.box[0]) * 1.3:
                rotated_cells.add(id(cell))
        all_cells.extend({id(cell): cell for row in table for cell in row}.values())
        if len(all_cells) > 1500:
            raise ImportProblem(
                "This image contains too many cells. Upload one smaller timetable section with its headings."
            )
        tables.append(table)
    if not tables:
        return (
            image,
            [],
            "Table borders were not clear enough. Use a straight, larger image with all headings. You can also enter missing rows manually.",
        )
    # Read the title to reject examination timetables before any draft can be imported.
    first_top = min(cell.box[1] for cell in all_cells)
    if first_top > 20:
        title = text_words(
            run_ocr(image.crop((0, 0, image.width, round(first_top))), psm=6)
        )
        if re.search(r"\bEXAM(?:INATION|INATIONS)?\b", title, re.I):
            raise ImportProblem(
                "This appears to be an examination timetable. Upload a lecture timetable image instead."
            )
    # Local thresholding in each crop handles grey photos without altering glyphs.
    read_cells(all_cells, cleaned, rotated_cells)
    reread_headings(tables, cleaned, rotated_cells)
    return image, tables, " ".join(dict.fromkeys(notes))
