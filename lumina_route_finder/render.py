"""Shared route drawing for CLI and GUI."""
import cv2
from .recognize import center


def render_route(board, path):
    """Render a zero-based node path without modifying the source board."""
    display = cv2.resize(board, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    for u, v in zip(path, path[1:]):
        a = tuple(2*x for x in center(u))
        b = tuple(2*x for x in center(v))
        cv2.arrowedLine(display, a, b, (0,60,255), 2, cv2.LINE_AA, tipLength=.18)
    for i, node in enumerate(path, 1):
        x,y = center(node)
        cv2.circle(display, (2*x,2*y), 10, (255,255,255), -1)
        cv2.putText(display, str(i), (2*x-9,2*y+5), cv2.FONT_HERSHEY_SIMPLEX, .4, (0,0,0), 1, cv2.LINE_AA)
    return display
