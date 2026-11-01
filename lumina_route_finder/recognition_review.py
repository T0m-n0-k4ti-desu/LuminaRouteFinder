"""Explicit, reversible edits of a validated recognized board."""
from copy import deepcopy
import cv2
from .recognize import candidates
from .domain.geometry import center
from .domain.catalog import CONTENT_NAMES

class RecognitionEditor:
    def __init__(self,snapshot,original=None):
        self.snapshot=deepcopy(snapshot);self.original=deepcopy(original if original is not None else snapshot);self.history=[]
    def remember(self):
        self.history.append(deepcopy(self.snapshot));self.history=self.history[-20:]
    def set_label(self,node,kind):
        node=tuple(node)
        if node not in self.snapshot.labels or (kind is not None and kind not in CONTENT_NAMES):raise ValueError('Invalid node or content type')
        self.remember();before=self.snapshot.labels[node];self.snapshot.labels[node]=kind
        self.snapshot.corrections.append({'kind':'content','node':[node[0]+1,node[1]+1],'before':before,'after':kind})
    def set_edge(self,u,v,present):
        u,v=tuple(u),tuple(v)
        if u[0]==v[0] and u[1]>v[1]:u,v=v,u
        if (u,v) not in set(candidates()) or not isinstance(present,bool):raise ValueError('Only actual adjacent horizontal/downward connections may be edited')
        self.remember();before=(u,v) in self.snapshot.edges
        self.snapshot.edges=[e for e in self.snapshot.edges if e!=(u,v)]
        if present:self.snapshot.edges.append((u,v))
        for diagnostic in self.snapshot.diagnostics:
            if tuple(diagnostic['from'])==u and tuple(diagnostic['to'])==v:diagnostic['state']='present' if present else 'absent'
        self.snapshot.pending_edges=[e for e in self.snapshot.pending_edges if tuple(map(tuple,e))!=(u,v)]
        self.snapshot.corrections.append({'kind':'edge','from':[u[0]+1,u[1]+1],'to':[v[0]+1,v[1]+1],'before':before,'after':present})
    def undo(self):
        if self.history:self.snapshot=self.history.pop()
    def reset(self):
        self.remember();self.snapshot=deepcopy(self.original)
    def missing_rows(self):
        return [r+1 for r in range(9) if not any(u[0]==r and v[0]==r+1 for u,v in self.snapshot.edges)]
    def confirm(self,acknowledge_gaps=False):
        if self.snapshot.pending_edges:raise ValueError('未確認の接続があります。「あり／なし」を各接続に指定してください。')
        if self.missing_rows() and not acknowledge_gaps:raise ValueError('接続がない段間を画像で確認し、確認チェックを付けてください。')
        self.snapshot.confirmed=True
        self.snapshot.corrections.append({'kind':'confirmation','missing_after_stages':self.missing_rows()})
        return deepcopy(self.snapshot)


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
