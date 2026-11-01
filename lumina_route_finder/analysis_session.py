"""One-image recognition cache and cooperative job control."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
from pathlib import Path

from .domain.jobs import AnalysisCancelled


def checkpoint(cancel=None,progress=None,stage=None):
    if cancel is not None and cancel.is_set():raise AnalysisCancelled()
    if progress is not None and stage:progress(stage)


@dataclass
class BoardSnapshot:
    board: object
    origin: tuple
    edges: list
    diagnostics: list
    score: float
    labels: dict
    content_diagnostics: list
    confirmed: bool=True
    pending_edges: list=field(default_factory=list)
    input_crop: object=None
    corrections: list=field(default_factory=list)


class AnalysisCache:
    def __init__(self):self.clear()
    def clear(self):
        self.key=self.snapshot=self.original=None;self.revision=getattr(self,'revision',0)+1
    def update(self,snapshot):
        self.snapshot=deepcopy(snapshot);self.revision+=1
    def signature(self,source,region):
        source=Path(source).resolve()
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        return str(source),digest,tuple(region) if region is not None else None
    def get(self,key):return deepcopy(self.snapshot) if self.key==key else None
    def put(self,key,snapshot):
        self.key=key;self.snapshot=deepcopy(snapshot);self.original=deepcopy(snapshot);self.revision+=1
