"""Read screenshot images copied by Windows Snipping Tool."""
from datetime import datetime
from pathlib import Path
import os
import tempfile
from PIL import Image, ImageGrab


def get_clipboard_image():
    value=ImageGrab.grabclipboard()
    if isinstance(value,Image.Image):
        value.load()
        return value.copy()
    return None  # Text and file lists are not screenshot pixels.


def save_clipboard_image(image, output_root):
    if not isinstance(image,Image.Image) or image.width<1 or image.height<1:
        raise ValueError('Clipboard does not contain an image.')
    folder=Path(output_root)/'clipboard'
    folder.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=datetime.now().strftime('clipboard_%Y%m%d_%H%M%S_'),suffix='.png',dir=folder)
    os.close(fd)
    path=Path(name)
    try:
        image.convert('RGB').save(path,format='PNG')
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path.resolve()
