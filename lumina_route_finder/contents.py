"""User-labelled mission icons and conservative matching on normalized boards."""
from functools import lru_cache
import cv2
import numpy as np
from .recognize import ASSETS, RecognitionError, center, issue, read_image

CONTENT_NAMES = {
    'element_tiles': '属性タイル渡り',
    'element_survival': '属性地形生存',
    'escape_room': 'エスケープルーム',
    'scales_of_sin': '罪悪の秤',
    'element_combat': '属性相性戦闘',
    'role_combat': '役割分担戦闘',
    'boss_mutation': 'ボス変異戦闘',
    'debuff_dispersion': 'デバフ分散',
    'two_faced_monarch': '両面の君主',
    'overheat_control': 'オーバーヒートコントロール',
    'ancient_weapon_core': '古代兵器の核破壊',
    'wheel_of_fate': '運命の輪',
}


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


def classify_contents(board):
    labels, diagnostics, uncertain = {}, [], []
    for row in range(10):
        for col in range(5):
            x,y = center((row,col))
            patch = board[y-13:y+14,x-13:x+14]
            scores = sorted(((max(float(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED).max()) for template in variants), key)
                             for key,variants in templates().items()), reverse=True)
            score,key = scores[0]
            margin = score-scores[1][0]
            diagnostics.append({'node':[row+1,col+1], 'content':key, 'score':score, 'margin':margin})
            if not np.isfinite(score) or score < .60 or margin < .08:
                uncertain.append(issue('AMBIGUOUS_CONTENT',
                                       f'Cannot identify mission at row {row+1}, column {col+1}.',
                                       (x-20,y-20,40,40)))
            labels[row,col] = key
    if uncertain:
        raise RecognitionError(uncertain, board)
    return labels, diagnostics
