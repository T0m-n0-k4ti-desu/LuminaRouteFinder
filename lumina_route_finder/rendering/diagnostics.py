"""Visualize reachable nodes, filtered edges and the deepest reachable stage."""
import cv2
from ..domain.geometry import center

def render_diagnostics(board,diagnostics):
    image=cv2.resize(board,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
    reachable=set(map(tuple,diagnostics['reachable_nodes']));blocked=set(map(tuple,diagnostics['blocked_nodes']))
    terminal=set(map(tuple,diagnostics['terminal_nodes']))
    for edge in diagnostics['frontier_edges']:
        points=[tuple(2*x for x in center((n[0]-1,n[1]-1))) for n in (edge['from'],edge['to'])]
        cv2.line(image,*points,(0,0,230),3,cv2.LINE_AA)
    for r in range(1,11):
        for c in range(1,6):
            node=(r,c);color=(120,120,120)
            if node in reachable:color=(0,180,0)
            if node in terminal:color=(0,180,255)
            if node in blocked:color=(0,0,230)
            x,y=center((r-1,c-1));cv2.circle(image,(2*x,2*y),15,color,3,cv2.LINE_AA)
    return image
