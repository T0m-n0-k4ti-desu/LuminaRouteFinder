"""Unicode-safe OpenCV file input and PNG output."""
import cv2
import numpy as np
from ..shared.errors import ErrorCode, RecognitionError, issue

def read_image(path):
    # imread on Windows does not reliably support Japanese paths.
    try:
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        image = None
    if image is None:
        raise RecognitionError([issue(ErrorCode.INPUT_READ_ERROR, 'Cannot read image.')])
    return image

def write_image(path, image):
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise OSError(f'Cannot encode {path}')
    data.tofile(str(path))
