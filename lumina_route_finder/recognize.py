"""Recognize connections on a located, validated canonical board.

Location and validation helpers remain importable here for existing callers.
"""
from functools import lru_cache
import cv2
import numpy as np
from .paths import ASSETS
from .errors import ErrorCode, RecognitionError, issue
from .image_io import read_image
from .domain.geometry import center
from .board_location import (locate, locate_details, locate_native, locate_scaled_header, visible_icon_count)
from .board_validation import validate

CONFIG_VERSION = 'scaled-header-grid-v4'


def candidates():
    for r in range(10):
        for c in range(5):
            if c < 4:
                yield (r,c), (r,c+1)
            if r < 9:
                for nc in range(max(0,c-1), min(5,c+2)):
                    yield (r,c), (r+1,nc)


@lru_cache(maxsize=256)
def edge_pixels(u, v):
    a, b = np.array(center(u),float), np.array(center(v),float)
    yy, xx = np.mgrid[0:500,0:260]
    dx, dy = b-a
    length2 = dx*dx+dy*dy
    t = ((xx-a[0])*dx+(yy-a[1])*dy)/length2
    distance = np.abs((xx-a[0])*dy-(yy-a[1])*dx)/np.sqrt(length2)
    mask = (distance <= 1.35) & (t > 0) & (t < 1)
    mask &= (np.abs(xx-a[0])+np.abs(yy-a[1]) > 21)
    mask &= (np.abs(xx-b[0])+np.abs(yy-b[1]) > 21)
    if dx and dy:
        mask &= np.abs(t-.5) > .09
    return np.flatnonzero(mask)


def dot_contrast(board):
    gray = cv2.cvtColor(board,cv2.COLOR_BGR2GRAY).astype(float)
    return (cv2.GaussianBlur(gray,(0,0),4)-gray).ravel()


def edge_score(board, u, v, contrast=None):
    values = dot_contrast(board) if contrast is None else contrast
    pixels = edge_pixels(u,v)
    return int(np.count_nonzero(values[pixels] > 16)), len(pixels)


def recognize(image, *, allow_uncertain=False):
    from .locate import normalize
    board, origin, header_score, scale = locate_details(image)
    context=normalize(image,origin,scale,margin=40)
    issues = validate(board,context,(-40,-40))
    if issues:
        raise RecognitionError(issues, board, origin)
    edges, diagnostics, uncertain = [], [], []
    contrast = dot_contrast(board)
    for u,v in candidates():
        score, area = edge_score(board,u,v,contrast)
        diagonal = u[0] != v[0] and u[1] != v[1]
        present = score >= (14 if diagonal else 6)
        ambiguous = (3 <= score < 14) if diagonal else (3 <= score < 6)
        state = 'uncertain' if ambiguous else ('present' if present else 'absent')
        diagnostics.append({'from':u,'to':v,'dark_pixels':score,'area':area,'state':state})
        if ambiguous:
            x1,y1=center(u); x2,y2=center(v)
            uncertain.append(issue(ErrorCode.AMBIGUOUS_CONNECTION, f'Uncertain connection {u} -> {v}.', (min(x1,x2)-3,min(y1,y2)-3,abs(x2-x1)+6,abs(y2-y1)+6)))
        if present:
            edges.append((u,v))
    if uncertain and not allow_uncertain:
        raise RecognitionError(uncertain,board,origin)
    if not allow_uncertain and any(not any(u[0] == r and v[0] == r+1 for u,v in edges) for r in range(9)):
        raise RecognitionError([issue(ErrorCode.AMBIGUOUS_CONNECTION,'Missing evidence between rows; complete board cannot be confirmed.')],board,origin)
    return board, origin, edges, diagnostics, header_score
