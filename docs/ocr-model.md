# Timetable image recognition model

Optispace uses the compact **PP-OCRv5 English mobile recognition model** from
[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR), distributed in ONNX format
by [RapidAI / RapidOCR](https://github.com/RapidAI/RapidOCR). The model recognizes
individual lines cropped from lecture timetable cells. It does not schedule
classes or decide room availability.

- File: `en_PP-OCRv5_rec_mobile.onnx`, approximately 7.6 MB.
- Distribution: [RapidOCR model repository, v3.10.0](https://www.modelscope.cn/models/RapidAI/RapidOCR/files?Revision=v3.10.0).
- [Exact download](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx).
- SHA-256: `c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8`.
- Licence: **Apache License 2.0**, stated by the [model distribution](https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/README.md)
  and [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE).
  The full licence is included in [licenses/ocr-model-Apache-2.0.txt](licenses/ocr-model-Apache-2.0.txt).
- Attribution: PaddlePaddle/PaddleOCR authors and RapidAI/RapidOCR contributors.
  The distributed model weights are used unchanged.

`scripts/install-image-model.py` downloads the pinned model during local setup
or the Docker build and verifies its checksum before installing it. The binary
is not committed to Git. There are no downloads during an upload request.

Inference runs through **ONNX Runtime** using its CPU provider with one thread;
OpenCV and Pillow handle cell geometry and image preparation. **Tesseract** with
its English model independently rereads headings. These dependencies are free
and installed with the application; no API key or paid OCR service is required.
Uploaded timetables are processed on the Optispace server, not sent to the model
hosting site. The RapidOCR Python package is not required at runtime.

Recognition scores help prioritize review and are not calibrated probabilities.
Small, blurred or cropped text can still be wrong even with a high score. An
administrator must check shared headings, review retained entries and confirm
image coverage before validation and application.
