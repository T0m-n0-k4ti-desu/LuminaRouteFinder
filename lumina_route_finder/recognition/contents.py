"""User-labelled mission icons and conservative matching on normalized boards."""
from functools import lru_cache
import cv2
import numpy as np
from ..shared.paths import ASSETS
from ..shared.errors import ErrorCode, RecognitionError, issue
from ..domain.geometry import center
from ..domain.catalog import CONTENT_NAMES
from ..storage.images import read_image



@lru_cache(maxsize=1)
def templates():
    # Use only the symbol, excluding the shared diamond border and game background.
    variants = {}
    for key in CONTENT_NAMES:
        image = read_image(ASSETS/'content_icons'/f'{key}.png')
        variants[key] = []
        for size in (40,42,44):
            resized = cv2.resize(image, (size,size))
            mid = size//2
            variants[key].append(resized[mid-10:mid+11,mid-10:mid+11])
    return variants


def classify_contents(board, *, strict=True):
    labels, diagnostics, uncertain = {}, [], []
    for row in range(10):
        for col in range(5):
            x,y = center((row,col))
            patch = board[y-13:y+14,x-13:x+14]
            scores = sorted(((max(float(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED).max()) for template in variants), key)
                             for key,variants in templates().items()), reverse=True)
            score,key = scores[0]
            margin = score-scores[1][0]
            if not np.isfinite(score) or score < .60 or margin < .08:
                uncertain.append(issue(ErrorCode.AMBIGUOUS_CONTENT,
                                       f'Cannot identify mission at row {row+1}, column {col+1}.',
                                       (x-20,y-20,40,40)))
                labels[row,col] = None
            else:
                labels[row,col] = key
            diagnostics.append({'node':[row+1,col+1], 'content':labels[row,col], 'score':score, 'margin':margin})
    if uncertain and strict:
        raise RecognitionError(uncertain, board)
    return labels, diagnostics
