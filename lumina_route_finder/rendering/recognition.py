"""Draw recognition diagnostics without changing the recognized board."""
import cv2
from ..domain.geometry import center

def render_recognition(snapshot,selected_node=None,selected_edge=None):
    display=cv2.resize(snapshot.board,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
    for d in snapshot.diagnostics:
        u,v=tuple(d['from']),tuple(d['to']);state=d['state']
        if state=='absent' and (u,v)!=selected_edge:continue
        color=(0,170,0) if state=='present' else (0,160,255)
        if (u,v)==selected_edge:color=(255,70,0)
        cv2.line(display,tuple(2*x for x in center(u)),tuple(2*x for x in center(v)),color,2,cv2.LINE_AA)
    # Explicit edits may contain connections absent from the original diagnostics.
    diagnosed={(tuple(d['from']),tuple(d['to'])) for d in snapshot.diagnostics}
    for u,v in snapshot.edges:
        if (u,v) not in diagnosed:cv2.line(display,tuple(2*x for x in center(u)),tuple(2*x for x in center(v)),(255,70,0),2)
    for node,kind in snapshot.labels.items():
        x,y=center(node);color=(0,150,255) if kind is None else (240,240,240)
        cv2.circle(display,(2*x,2*y),12,color,2)
        cv2.putText(display,f'{node[0]+1},{node[1]+1}',(2*x-14,2*y+4),cv2.FONT_HERSHEY_SIMPLEX,.32,(10,10,10),1,cv2.LINE_AA)
    if selected_node is not None:
        x,y=center(selected_node);cv2.circle(display,(2*x,2*y),19,(255,80,0),3)
    return display
