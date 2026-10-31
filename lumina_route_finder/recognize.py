"""Locate scaled Lumina windows and recognize their normalized boards."""
from pathlib import Path
from functools import lru_cache
import cv2
import numpy as np

ASSETS = Path(__file__).parent / 'assets'
CONFIG_VERSION = 'normalized-layout-v2'


class RecognitionError(Exception):
    def __init__(self, issues, board=None, origin=None):
        self.issues, self.board, self.origin = issues, board, origin
        super().__init__('; '.join(i['code'] for i in issues))


def issue(code, message, box=None):
    item = {'code': code, 'message': message}
    if box is not None:
        item['board_box'] = list(map(int, box))
    return item


def read_image(path):
    # imread on Windows does not reliably support Japanese paths.
    try:
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        image = None
    if image is None:
        raise RecognitionError([issue('INPUT_READ_ERROR', 'Cannot read image.')])
    return image


def _locate(image):
    """Find the window at 0.5–3x scale, then normalize only its board context."""
    template = read_image(ASSETS / 'window.png')
    h, w = template.shape[:2]
    # Search a reduced image first so large screenshots do not multiply the cost.
    reduction = min(1., 1920 / image.shape[1])
    search = cv2.resize(image, None, fx=reduction, fy=reduction,
                        interpolation=cv2.INTER_AREA) if reduction < 1 else image

    def match(scale, source, factor):
        width, height = round(w*scale*factor), round(h*scale*factor)
        if width < 2 or height < 2 or width > source.shape[1] or height > source.shape[0]:
            return None
        resized = cv2.resize(template, (width, height), interpolation=cv2.INTER_LINEAR)
        scores = cv2.matchTemplate(source, resized, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(scores)
        return score, x/factor, y/factor, scale, scores

    coarse = [m[:4] for scale in np.arange(.5, 3.001, .05)
              if (m := match(float(scale), search, reduction)) is not None]
    if not coarse:
        raise RecognitionError([issue('BOARD_NOT_FOUND', 'Window header not found.')])
    best = max(coarse, key=lambda m: m[0])
    # Refine scale at original resolution to retain thin text and icon outlines.
    refined = None
    for candidate_scale in np.arange(max(.5, best[3]-.05), min(3., best[3]+.05)+.001, .005):
        candidate = match(float(candidate_scale), image, 1.)
        if candidate is not None and (refined is None or candidate[0] > refined[0]):
            refined = candidate
    score, x, y, scale, scores = refined
    if score < .88:
        raise RecognitionError([issue('BOARD_NOT_FOUND', 'Window header not found at 0.5–3x scale.')])
    for candidate in coarse:
        other_score, cx, cy, cs = candidate
        if other_score >= .88 and (abs(cx-x) > w*scale/2 or abs(cy-y) > h*scale*2):
            raise RecognitionError([issue('MULTIPLE_BOARDS', 'Multiple matching windows found.')])
    ih, iw = round(h*scale), round(w*scale)
    scores[max(0,round(y)-ih):round(y)+ih, max(0,round(x)-iw):round(x)+iw] = -1
    if scores.max() >= .88:
        raise RecognitionError([issue('MULTIPLE_BOARDS', 'Multiple matching windows found.')])
    ox, oy = x + 82*scale, y + 90*scale
    if ox < 0 or oy < 0 or ox+260*scale > image.shape[1] or oy+500*scale > image.shape[0]:
        raise RecognitionError([issue('BOARD_NOT_FOUND', 'Board is cropped.')])
    # Keep a margin for cursors partly outside the board. All subsequent geometry
    # (icons, lines, cursor and diagnostic boxes) uses canonical board pixels.
    transform = np.array([[1/scale, 0, 40-ox/scale],
                          [0, 1/scale, 40-oy/scale]], dtype=np.float64)
    context = cv2.warpAffine(image, transform, (340, 580), flags=cv2.INTER_LINEAR)
    board = context[40:540, 40:300].copy()
    return board, (round(ox), round(oy)), float(score), context


def locate(image):
    board, origin, score, _ = _locate(image)
    return board, origin, score


def validate(board, cursor_image=None, cursor_offset=(0,0)):
    issues = []
    gray = cv2.cvtColor(board, cv2.COLOR_BGR2GRAY).astype(float)
    yy, xx = np.mgrid[-22:23,-22:23]
    dist = np.abs(xx)+np.abs(yy)
    for r in range(10):
        for c in range(5):
            x,y=center((r,c))
            patch=gray[y-22:y+23,x-22:x+23]
            # The pale diamond rim must be brighter than its inner border.
            rim=float(patch[dist == 18].mean()-patch[dist == 16].mean())
            if rim < 12:
                issues.append(issue('INVALID_BOARD_STRUCTURE', f'Icon outline missing at row {r+1}, column {c+1}.', (x-22,y-22,44,44)))
    # Strong blue selection outline is distinct from the pale blue background.
    hsv = cv2.cvtColor(board, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (95, 140, 130), (115, 255, 255))
    for r in range(1, 10):
        for c in range(5):
            x, y = 29 + 50*c, 25 + 50*r
            yy, xx = np.mgrid[max(0,y-24):min(500,y+25),max(0,x-24):min(260,x+25)]
            ring = (np.abs(xx-x)+np.abs(yy-y) >= 19) & (np.abs(xx-x)+np.abs(yy-y) <= 26)
            values = blue[max(0,y-24):min(500,y+25),max(0,x-24):min(260,x+25)]
            if np.count_nonzero(values[ring]) >= 30:
                issues.append(issue('INCOMPLETE_BOARD', f'Lower-row selection at row {r+1}, column {c+1}. Clear selection.', (x-24,y-24,48,48)))
    cursor_image = board if cursor_image is None else cursor_image
    template = read_image(ASSETS / 'cursor.png')
    # Use saturated purple border only, excluding background and pale interior.
    th = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(th, (115, 45, 35), (165, 255, 240))
    scores = cv2.matchTemplate(cursor_image, template, cv2.TM_CCORR_NORMED, mask=mask)
    scores = np.nan_to_num(scores, nan=0, posinf=0, neginf=0)
    _, score, _, (x,y) = cv2.minMaxLoc(scores)
    # The color correlation of an absent cursor can be high; also require its
    # distinctive dark triangular border to match in absolute color.
    patch = cursor_image[y:y+template.shape[0],x:x+template.shape[1]]
    delta = np.mean(np.abs(patch.astype(float)-template.astype(float))[mask > 0])
    x += cursor_offset[0]
    y += cursor_offset[1]
    overlaps = x < 260 and y < 500 and x+template.shape[1] > 0 and y+template.shape[0] > 0
    if score > .97 and delta < 23 and overlaps:
        issues.append(issue('CURSOR_OCCLUSION', 'Move the cursor outside the board.', (x-3,y-3,template.shape[1]+6,template.shape[0]+6)))
    if any(i['code'] == 'INCOMPLETE_BOARD' for i in issues):
        issues = [i for i in issues if i['code'] != 'INVALID_BOARD_STRUCTURE']
    return issues


def center(node):
    r, c = node
    return 29 + 50*c, 25 + 50*r


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


def recognize(image):
    board, origin, header_score, context = _locate(image)
    issues = validate(board, context, (-40, -40))
    if issues:
        raise RecognitionError(issues, board, origin)
    edges, diagnostics, uncertain = [], [], []
    contrast = dot_contrast(board)
    for u,v in candidates():
        score, area = edge_score(board,u,v,contrast)
        diagonal = u[0] != v[0] and u[1] != v[1]
        present = score >= (14 if diagonal else 6)
        ambiguous = (2 <= score < 14) if diagonal else (2 <= score < 6)
        state = 'uncertain' if ambiguous else ('present' if present else 'absent')
        diagnostics.append({'from':u,'to':v,'dark_pixels':score,'area':area,'state':state})
        if ambiguous:
            x1,y1=center(u); x2,y2=center(v)
            uncertain.append(issue('AMBIGUOUS_CONNECTION', f'Uncertain connection {u} -> {v}.', (min(x1,x2)-3,min(y1,y2)-3,abs(x2-x1)+6,abs(y2-y1)+6)))
        if present:
            edges.append((u,v))
    if uncertain:
        raise RecognitionError(uncertain,board,origin)
    if any(not any(u[0] == r and v[0] == r+1 for u,v in edges) for r in range(9)):
        raise RecognitionError([issue('AMBIGUOUS_CONNECTION','Missing evidence between rows; complete board cannot be confirmed.')],board,origin)
    return board, origin, edges, diagnostics, header_score
