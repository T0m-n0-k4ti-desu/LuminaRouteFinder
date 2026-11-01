"""Explicit, reversible edits of a validated recognized board."""
from copy import deepcopy
from ..domain.geometry import candidates
from ..domain.catalog import CONTENT_NAMES

class RecognitionEditor:
    def __init__(self,snapshot,original=None):
        self.snapshot=deepcopy(snapshot);self.original=deepcopy(original if original is not None else snapshot);self.history=[]
    def remember(self):
        self.history.append(deepcopy(self.snapshot,{id(self.snapshot.board):self.snapshot.board,id(self.snapshot.input_crop):self.snapshot.input_crop}));self.history=self.history[-20:]
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




def __getattr__(name):
    # Keep the previous helper available without coupling the editor to OpenCV.
    if name=='render_recognition':
        from ..rendering.recognition import render_recognition
        return render_recognition
    raise AttributeError(name)
