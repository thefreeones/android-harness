"""Text recognition over phone screenshots via PaddleOCR.

Primary backend: PaddleOCR 2.x (best Chinese accuracy).
Auto-detects GPU. Includes dark-mode preprocessing for better
accuracy on dark-themed UIs (ColorOS, MIUI dark mode, etc.).

This is android-harness's element tree: OCR gives every visible string
a bounding box in native screen coordinates, ready for tap().
"""

import logging
import os
import time
from pathlib import Path

from .capture import screenshot

logging.getLogger("ppocr").setLevel(logging.WARNING)
logging.getLogger("paddle").setLevel(logging.WARNING)

_READER = None
_READER_BACKEND = None
_READER_GPU = None
_GPU_AVAILABLE = None


def _check_gpu():
    """Check if PaddlePaddle GPU is available."""
    global _GPU_AVAILABLE
    if _GPU_AVAILABLE is not None:
        return _GPU_AVAILABLE
    try:
        import paddle
        _GPU_AVAILABLE = (
            paddle.is_compiled_with_cuda()
            and paddle.device.get_device().startswith("gpu")
        )
    except Exception:
        _GPU_AVAILABLE = False
    return _GPU_AVAILABLE


def _preprocess_image(image_path):
    """Preprocess screenshot for better OCR accuracy.

    Detects dark-mode screenshots (avg brightness < 100) and applies:
    1. Color inversion (dark background -> light background)
    2. Contrast enhancement

    Returns path to preprocessed image (original if already light mode).
    """
    from PIL import Image, ImageOps, ImageEnhance

    img = Image.open(image_path).convert("RGB")
    gray = img.convert("L")
    pixels = list(gray.getdata())
    avg_brightness = sum(pixels) / len(pixels)

    if avg_brightness >= 50:
        return image_path  # not dark enough, skip (avoids harming wallpapers)

    # Dark mode: invert + enhance contrast
    inverted = ImageOps.invert(img)
    enhancer = ImageEnhance.Contrast(inverted)
    enhanced = enhancer.enhance(1.3)

    out_path = str(Path(image_path).parent / f"_pp_{Path(image_path).name}")
    enhanced.save(out_path, "PNG")
    return out_path


def _get_reader(backend=None, gpu=None):
    """Lazy-init OCR reader. Caches across calls.

    Args:
        backend: 'paddleocr' (default) or 'easyocr' (fallback).
        gpu: Force GPU on/off. Default: auto-detect GPU, fallback to CPU.
    """
    global _READER, _READER_BACKEND, _READER_GPU
    backend = backend or "paddleocr"

    if gpu is None:
        gpu = _check_gpu()

    if (
        _READER is not None
        and _READER_BACKEND == backend
        and _READER_GPU == gpu
    ):
        return _READER

    if backend == "paddleocr":
        from paddleocr import PaddleOCR

        mode = "GPU" if gpu else "CPU"
        _READER = PaddleOCR(
            lang="ch",
            use_angle_cls=True,
            use_gpu=gpu,
            show_log=False,
        )
    else:
        import easyocr

        mode = "GPU (EasyOCR)" if gpu else "CPU (EasyOCR)"
        _READER = easyocr.Reader(
            ["ch_sim", "en"], gpu=gpu if gpu is not None else True, verbose=False
        )

    _READER_BACKEND, _READER_GPU = backend, gpu
    return _READER


def _paddle_results(reader, image_path, min_confidence):
    """Convert PaddleOCR 2.x results to unified format.

    PaddleOCR 2.x returns: [[[bbox], (text, confidence)], ...]
    """
    raw = reader.ocr(image_path, cls=True)
    out = []
    if raw and raw[0]:
        for line in raw[0]:
            bbox = line[0]
            text = line[1][0]
            conf = line[1][1]
            if conf < min_confidence:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            out.append(
                {
                    "text": text,
                    "confidence": round(float(conf), 3),
                    "x": round((min(xs) + max(xs)) / 2, 1),
                    "y": round((min(ys) + max(ys)) / 2, 1),
                    "w": round(max(xs) - min(xs), 1),
                    "h": round(max(ys) - min(ys), 1),
                }
            )
    return out


def ocr(min_confidence=0.3, backend=None, gpu=None, image_path=None,
        preprocess=True):
    """All visible text with tap-ready centers in native screen coords.

    Returns: [{text, confidence, x, y, w, h}]
      - (x, y) is the box center -- pass straight to tap().
      - coordinates are in Android native screen points.

    Args:
        min_confidence: Filter results below this threshold (0.0-1.0).
        backend: 'paddleocr' (default) or 'easyocr'.
        gpu: Force GPU on/off. Default: auto-detect.
        image_path: Path to an existing screenshot. If None, captures fresh.
        preprocess: Apply dark-mode inversion. Default True.
    """
    reader = _get_reader(backend=backend, gpu=gpu)
    img = image_path or screenshot()

    if preprocess:
        img = _preprocess_image(img)

    backend = backend or "paddleocr"
    if backend == "paddleocr":
        return _paddle_results(reader, img, min_confidence)
    else:
        import easyocr

        raw = reader.readtext(img)
        out = []
        for bbox, text, conf in raw:
            if conf < min_confidence:
                continue
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            out.append(
                {
                    "text": text,
                    "confidence": round(float(conf), 3),
                    "x": round((min(xs) + max(xs)) / 2, 1),
                    "y": round((min(ys) + max(ys)) / 2, 1),
                    "w": round(max(xs) - min(xs), 1),
                    "h": round(max(ys) - min(ys), 1),
                }
            )
        return out


def find_text(query, exact=False, min_confidence=0.3, image_path=None,
              backend=None, gpu=None, preprocess=True):
    """OCR results matching query (case-insensitive substring by default).

    Returns list of [{text, confidence, x, y, w, h}].
    """
    q = query.lower()
    hits = []
    for o in ocr(
        min_confidence=min_confidence,
        image_path=image_path,
        backend=backend,
        gpu=gpu,
        preprocess=preprocess,
    ):
        t = o["text"].lower()
        if exact:
            if t == q:
                hits.append(o)
        else:
            if q in t:
                hits.append(o)
    return hits
