"""Validate icon structure, selection state and cursor occlusion."""
import cv2
import numpy as np
from .paths import ASSETS
from .errors import RecognitionError, issue
from .image_io import read_image
from .domain.geometry import center


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
            selected_top=False
            if r==0:
                patch_color=board[y-24:y+25,x-24:x+25]
                h=cv2.cvtColor(patch_color,cv2.COLOR_BGR2HSV)
                blue_top=cv2.inRange(h,(95,140,130),(115,255,255))
                yy_top,xx_top=np.mgrid[-24:25,-24:25]
                ring_top=(np.abs(xx_top)+np.abs(yy_top)>=19)&(np.abs(xx_top)+np.abs(yy_top)<=26)
                selected_top=np.count_nonzero(blue_top[ring_top])>=30
            if rim < 12 and not selected_top:
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
    # Absolute masked error is stable after resampling; color correlation can
    # prefer a purple icon over a slightly blurred cursor.
    scores = cv2.matchTemplate(cursor_image, template, cv2.TM_SQDIFF, mask=mask)
    score, _, (x,y), _ = cv2.minMaxLoc(scores)
    rms = np.sqrt(max(0,score)/(np.count_nonzero(mask)*3))
    patch = cursor_image[y:y+template.shape[0],x:x+template.shape[1]]
    delta = np.mean(np.abs(patch.astype(float)-template.astype(float))[mask > 0])
    x += cursor_offset[0]
    y += cursor_offset[1]
    overlaps = x < 260 and y < 500 and x+template.shape[1] > 0 and y+template.shape[0] > 0
    if rms < 42 and delta < 30 and overlaps:
        issues.append(issue('CURSOR_OCCLUSION', 'Move the cursor outside the board.', (x-3,y-3,template.shape[1]+6,template.shape[0]+6)))
    if any(i['code'] == 'INCOMPLETE_BOARD' for i in issues):
        issues = [i for i in issues if i['code'] != 'INVALID_BOARD_STRUCTURE']
    return issues
