"""Shared image-analysis use cases for CLI and desktop controllers.

The shell coordinates recognition, pure route rules and output adapters. It has
no dependency on argument parsing or Tk, so both entry points use the same flow.
"""
from datetime import datetime
from pathlib import Path
import tempfile
from ..shared.errors import ApplicationError, ErrorCode, RecognitionError, issue, error_result
from ..storage.images import read_image, write_image
from ..recognition.connections import CONFIG_VERSION, recognize
from ..domain.solver import solve
from ..domain.geometry import export_solution
from .session import AnalysisCache, BoardSnapshot, checkpoint
from ..domain.geometry import center
from ..storage.artifacts import write_analysis_artifacts, write_error_artifact, write_result


def run_image(source, destination, limit=20, region=None, *, avoid_repeated=False, excluded_types=(), fallback_priority='stage', cache=None, cancel=None, progress=None, objective='count', weights=None):
    destination.mkdir(parents=True,exist_ok=True)
    result = {'input': str(source.resolve()), 'config_version': CONFIG_VERSION,
              'coordinate_system': '1-based [row,column]',
              'assumptions': {'revisit':False,'horizontal_in_first_and_last_rows':True}}
    try:
        checkpoint(cancel,progress,'画像確認中')
        try:key=cache.signature(source,region) if cache is not None else None
        except OSError as exc:raise RecognitionError([issue(ErrorCode.INPUT_READ_ERROR,str(exc))]) from exc
        snapshot=cache.get(key) if cache is not None else None
        reused=snapshot is not None
        if snapshot is None:
            input_image=read_image(source)
            offset=(0,0)
            if region is not None:
                if len(region)!=4 or any(not isinstance(v,int) for v in region):
                    raise RecognitionError([issue(ErrorCode.INVALID_REGION,'Region must contain four integer coordinates.')])
                x1,y1,x2,y2=region
                h,w=input_image.shape[:2]
                if not (0<=x1<x2<=w and 0<=y1<y2<=h and x2-x1>=20 and y2-y1>=20):
                    raise RecognitionError([issue(ErrorCode.INVALID_REGION,'Region is empty, too small or outside the input image.')])
                input_image=input_image[y1:y2,x1:x2].copy();offset=(x1,y1)
            checkpoint(cancel,progress,'盤面・接続を認識中')
            try:
                board,origin,edges,diagnostics,score=recognize(input_image)
                needs_review=False
            except RecognitionError as exc:
                if cache is None or not exc.issues or any(i['code']!='AMBIGUOUS_CONNECTION' for i in exc.issues):raise
                # Validation still rejects hidden/occluded/incomplete boards. Only
                # ambiguous connections may be retained for explicit human review.
                board,origin,edges,diagnostics,score=recognize(input_image,allow_uncertain=True)
                needs_review=True
                review_issues=exc.issues
            origin=(origin[0]+offset[0],origin[1]+offset[1])
            checkpoint(cancel,progress,'コンテンツを判定中')
            from ..recognition.contents import classify_contents
            labels,content_diagnostics=classify_contents(board,strict=False)
            snapshot=BoardSnapshot(board,origin,edges,diagnostics,score,labels,content_diagnostics,input_crop=input_image.copy() if region else None)
            if needs_review:
                snapshot.confirmed=False
                snapshot.pending_edges=[(tuple(d['from']),tuple(d['to'])) for d in diagnostics if d['state']=='uncertain']
            checkpoint(cancel)
            if cache is not None:cache.put(key,snapshot)
            if needs_review:raise RecognitionError(review_issues,board,origin)
        else:checkpoint(cancel,progress,'認識結果を再利用')
        if not snapshot.confirmed:raise RecognitionError([issue(ErrorCode.AMBIGUOUS_CONNECTION,'Manual confirmation is required.')],snapshot.board,snapshot.origin)
        board,origin,edges,diagnostics,score=snapshot.board,snapshot.origin,snapshot.edges,snapshot.diagnostics,snapshot.score
        labels,content_diagnostics=snapshot.labels,snapshot.content_diagnostics
        if region is not None:
            result['input_region']=list(region)
            # Only a fresh crop is written; reuse does not decode the source again.
            write_image(destination/'input.png',snapshot.input_crop)
        from ..domain.catalog import CONTENT_NAMES
        excluded_types = tuple(excluded_types)
        if any(key not in CONTENT_NAMES for key in excluded_types):
            raise ApplicationError([issue(ErrorCode.INVALID_CONTENT_TYPE, 'Unknown excluded content type')])
        filtered = bool(avoid_repeated or excluded_types or objective!='count')
        if filtered and any(value is None for value in labels.values()):
            issues=[]
            for node,value in labels.items():
                if value is None:
                    x,y=center(node)
                    issues.append(issue(ErrorCode.AMBIGUOUS_CONTENT,'Cannot identify mission type.',(x-20,y-20,40,40)))
            raise RecognitionError(issues,board)
        result['content_types'] = [[labels[r,c] for c in range(5)] for r in range(10)]
        result['content_diagnostics'] = content_diagnostics
        if filtered:
            result['filters'] = {'avoid_repeated':avoid_repeated, 'excluded_types':list(excluded_types)}
        checkpoint(cancel,progress,'経路を探索中')
        solved = solve([(r,c) for r in range(10) for c in range(5)],edges,limit,
                       node_types=labels, excluded_types=excluded_types, avoid_repeated=avoid_repeated, fallback_priority=fallback_priority,cancel=cancel,objective=objective,weights=weights)
        result.update(export_solution(solved))
        result['weights']=dict(weights or {})
        result['recognition_reused']=reused
        result['manual_corrections']=snapshot.corrections
        if solved['status'] in ('partial','no_path'):
            from ..domain.diagnostics import diagnose
            from ..rendering.diagnostics import render_diagnostics
            options={'avoid_repeated':avoid_repeated,'exclude_enabled':bool(excluded_types),'excluded_types':list(excluded_types),'objective':objective}
            diagnostic=diagnose(labels.keys(),edges,labels,options)
            result['unreachable_diagnostics']=diagnostic
            write_image(destination/'diagnostic.png',render_diagnostics(board,diagnostic))
        result['board_origin'] = origin
        result['board_match'] = score
        checkpoint(cancel,progress,'結果を書き出し中')
        write_analysis_artifacts(destination, board, edges, diagnostics, solved)
    except ApplicationError as exc:
        result.update(error_result(exc))
        write_error_artifact(destination, exc)
    write_result(destination, result)
    return result


def analyze_file(source, output_root, limit=20, region=None, on_created=None, *, avoid_repeated=False, excluded_types=(), fallback_priority='stage', cache=None, cancel=None, progress=None, objective='count', weights=None):
    """Run analysis into a newly allocated folder; no earlier result is overwritten."""
    source, output_root = Path(source), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = datetime.now().strftime('%Y%m%d_%H%M%S_')
    destination = Path(tempfile.mkdtemp(prefix=prefix, dir=output_root))
    if on_created is not None:
        on_created(destination)
    result = run_image(source, destination, limit=limit, region=region,
                       avoid_repeated=avoid_repeated, excluded_types=excluded_types, fallback_priority=fallback_priority,cache=cache,cancel=cancel,progress=progress,objective=objective,weights=weights)
    name = 'error.png' if result['status'] == 'error' else ('board.png' if result['status'] in ('ok','partial') else 'route.png')
    preview = destination / name
    if not preview.is_file():
        preview = destination/'input.png' if (destination/'input.png').is_file() else source
    try:
        image = read_image(preview)
    except RecognitionError:
        image = None
    return result, destination, image
