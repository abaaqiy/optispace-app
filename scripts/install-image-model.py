#!/usr/bin/env python3
"""Install the pinned, free PP-OCRv5 English recognition model before startup."""

import argparse
import hashlib
from pathlib import Path
import tempfile
from urllib.request import urlopen

MODEL_URL = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx"
MODEL_SHA256 = "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "backend/scheduling/ocr_models",
    )
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    destination = args.directory / "english.onnx"
    if (
        destination.exists()
        and hashlib.sha256(destination.read_bytes()).hexdigest() == MODEL_SHA256
    ):
        print("Image recognition model is installed and verified.")
        return
    with urlopen(MODEL_URL, timeout=60) as response:
        content = response.read(20 * 1024 * 1024 + 1)
    if (
        len(content) > 20 * 1024 * 1024
        or hashlib.sha256(content).hexdigest() != MODEL_SHA256
    ):
        raise SystemExit(
            "Image model download failed integrity verification; nothing installed."
        )
    with tempfile.NamedTemporaryFile(dir=args.directory, delete=False) as temporary:
        temporary.write(content)
        staging = Path(temporary.name)
    staging.chmod(0o644)
    staging.replace(destination)
    print("Image recognition model installed and verified.")


if __name__ == "__main__":
    main()
