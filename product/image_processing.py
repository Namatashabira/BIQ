import os
from io import BytesIO
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageOps
from django.core.files.uploadedfile import InMemoryUploadedFile

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def _strip_near_white_background(image: Image.Image, threshold: int = 245) -> Image.Image:
    """Make near-white background transparent to soften hard edges."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    data = np.array(image)

    if data.shape[2] == 3:
        alpha = np.full((data.shape[0], data.shape[1], 1), 255, dtype=np.uint8)
        data = np.concatenate([data, alpha], axis=2)

    rgb = data[..., :3]
    near_white = (rgb > threshold).all(axis=2)
    low_variance = (rgb.max(axis=2) - rgb.min(axis=2)) < 12
    mask = near_white & low_variance

    data[..., 3][mask] = 0

    return Image.fromarray(data, mode="RGBA")


def process_product_image(
    uploaded_file,
    max_size: Tuple[int, int] = (1600, 1600),
    bg_threshold: int = 245,
    webp_quality: int = 82,
):
    """
    Normalize a product image by:
    - respecting EXIF orientation
    - stripping near-white backgrounds
    - resizing to a sane max dimension
    - compressing to WebP
    """
    if not uploaded_file:
        return uploaded_file

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image)

        processed = _strip_near_white_background(image, threshold=bg_threshold)
        processed.thumbnail(max_size, RESAMPLE)

        buffer = BytesIO()
        processed.save(buffer, format="WEBP", quality=webp_quality, method=6, optimize=True)
        buffer.seek(0)

        base_name = Path(uploaded_file.name).stem or "product-image"
        new_name = f"{base_name}.webp"

        return InMemoryUploadedFile(
            buffer,
            field_name=getattr(uploaded_file, "field_name", None),
            name=new_name,
            content_type="image/webp",
            size=buffer.getbuffer().nbytes,
            charset=None,
        )
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return uploaded_file
