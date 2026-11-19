import io
import rembg
from PIL import Image, ImageOps


IMG_FORMATS = {"PNG", "JPEG", "WEBP", "JPG"}  # Allowed formats
MAX_SIZE = 7 * 1024 * 1024  # 7 MB max to avoid DoS

_session = None

def clear_all_metadata(img_bytes: bytes):
    if len(img_bytes) > MAX_SIZE:
        raise ValueError("File is too large")

    try:
        img = Image.open(io.BytesIO(img_bytes))
    except (Image.UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError("Invalid or oversized image") from error

    with img:
        if img.format not in IMG_FORMATS:
            raise ValueError("Unsupported format")

        fmt = img.format
        safe_img = ImageOps.exif_transpose(img)
        safe_img.info.clear()

        out = io.BytesIO()
        safe_img.save(out, fmt)

    return out.getvalue()


def resize_image(img_bytes: bytes, size=(300, 300)) -> bytes:
    with Image.open(io.BytesIO(img_bytes)) as img:
        img = img.convert("RGBA")
        # Keeps aspect ratio 
        res = ImageOps.contain(img, size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        res.save(out, format="PNG")
        return out.getvalue()


def remove_background(img_bytes: bytes) -> bytes:
    global _session
    if _session is None:
        _session = rembg.new_session("u2net")
    return rembg.remove(img_bytes, session=_session)


def process_image(img_bytes: bytes) -> bytes:
    clean = clear_all_metadata(img_bytes)
    small = resize_image(clean)          # resize before rembg: much faster
    return remove_background(small)      # final output is PNG