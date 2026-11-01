"""Header search and grid-based board location, with original-image coordinates."""
import cv2
import numpy as np
from ..shared.paths import ASSETS
from ..shared.errors import ErrorCode, RecognitionError, issue
from ..storage.images import read_image
from ..domain.geometry import center
from .validation import validate


def locate_native(image):
    template = read_image(ASSETS / 'window.png')
    h, w = template.shape[:2]
    if image.shape[0] < h or image.shape[1] < w:
        raise RecognitionError([issue(ErrorCode.BOARD_NOT_FOUND, 'Window header not found.')])
    scores = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    matches=[]
    while len(matches)<12:
        _,score,_,(x,y)=cv2.minMaxLoc(scores)
        if score<.88:
            break
        scores[max(0,y-h):y+h,max(0,x-w//2):x+w//2]=-1
        ox,oy=x+82,y+90
        if ox<0 or oy<0 or ox+260>image.shape[1] or oy+500>image.shape[0]:
            continue
        board=image[oy:oy+500,ox:ox+260].copy()
        # A matching title on a covered window is not a second visible board.
        if visible_icon_count(board)<43:
            continue
        matches.append((board,(ox,oy),float(score)))
    if len(matches)>1:
        raise RecognitionError([issue(ErrorCode.MULTIPLE_BOARDS,'Multiple complete visible boards found.')])
    if not matches:
        raise RecognitionError([issue(ErrorCode.BOARD_NOT_FOUND,'No complete visible board under a matching header.')])
    return matches[0]


def locate_scaled_header(image):
    """Recover a board from its scaled header when lattice detection fails."""
    from .grid import normalize
    template = read_image(ASSETS / 'window.png')
    h, w = template.shape[:2]
    reduction = min(1., 1920 / image.shape[1])
    search = cv2.resize(image, None, fx=reduction, fy=reduction,
                        interpolation=cv2.INTER_AREA) if reduction < 1 else image

    def match(scale, source, factor):
        width, height = round(w*scale*factor), round(h*scale*factor)
        if width < 2 or height < 2 or width > source.shape[1] or height > source.shape[0]:
            return None
        resized = cv2.resize(template, (width, height), interpolation=cv2.INTER_LINEAR)
        scores = cv2.matchTemplate(source, resized, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(scores)
        return score, scale, scores

    coarse = [m[:2] for scale in np.arange(.5, 3.001, .05)
              if (m := match(float(scale), search, reduction)) is not None]
    matches = []
    # Refine each promising scale, including separate windows at different scales.
    # A low coarse score may recover at full resolution, so always refine the best.
    scales = [scale for score, scale in coarse if score >= .88]
    if coarse:
        scales.append(max(coarse)[1])
    refined_scales = set()
    for coarse_scale in scales:
        best = None
        for step in range(max(100, round((coarse_scale-.05)*200)),
                          min(600, round((coarse_scale+.05)*200))+1):
            if step in refined_scales:
                continue
            refined_scales.add(step)
            candidate = match(step/200, image, 1.)
            if candidate is not None and (best is None or candidate[0] > best[0]):
                best = candidate
        if best is None or best[0] < .88:
            continue
        _, scale, scores = best
        ih, iw = round(h*scale), round(w*scale)
        for _ in range(12):
            _, score, _, (x, y) = cv2.minMaxLoc(scores)
            if score < .88:
                break
            scores[max(0,y-ih):y+ih, max(0,x-iw//2):x+iw//2] = -1
            origin = (x+82*scale, y+90*scale)
            ox, oy = origin
            if ox+260*scale > image.shape[1] or oy+500*scale > image.shape[0]:
                continue
            board = normalize(image, origin, (scale, scale))
            # Match main's handling of covered titles: require a visible board.
            if visible_icon_count(board) < 43:
                continue
            if any(abs(ox-m[1][0]) < 25*scale and abs(oy-m[1][1]) < 25*scale
                   for m in matches):
                continue
            matches.append((board, origin, float(score), (scale, scale)))
    if len(matches) > 1:
        raise RecognitionError([issue(ErrorCode.MULTIPLE_BOARDS, 'Multiple complete scaled windows found.')])
    if not matches:
        raise RecognitionError([issue(ErrorCode.BOARD_NOT_FOUND, 'Window header not found at 0.5–3x scale.')])
    return matches[0]


def visible_icon_count(board):
    gray=cv2.cvtColor(board,cv2.COLOR_BGR2GRAY).astype(float)
    yy,xx=np.mgrid[-22:23,-22:23]
    dist=np.abs(xx)+np.abs(yy)
    count=0
    for r in range(10):
        for c in range(5):
            x,y=center((r,c))
            patch=gray[y-22:y+23,x-22:x+23]
            count+=float(patch[dist==18].mean()-patch[dist==16].mean())>=12
    return count


def locate_details(image):
    from .grid import find_grids, normalize
    native = None
    try:
        board,origin,score=locate_native(image)
        native = (board,origin,score,(1.,1.))
        if score >= .99:
            return native
    except RecognitionError as exc:
        if exc.issues[0]['code'] == ErrorCode.MULTIPLE_BOARDS:
            raise
    grids=find_grids(image)
    if len(grids)>1:
        raise RecognitionError([issue(ErrorCode.MULTIPLE_BOARDS,'Multiple complete icon grids found.')])
    if not grids and native is not None:
        if not validate(native[0]):
            return native
    if not grids:
        return locate_scaled_header(image)
    origin,scale,score=grids[0]
    return normalize(image,origin,scale),origin,score,scale


def locate(image):
    board,origin,score,_=locate_details(image)
    return board,origin,score
