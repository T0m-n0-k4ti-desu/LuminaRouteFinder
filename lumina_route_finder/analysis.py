"""Shared image-analysis use cases for CLI and desktop controllers.

The shell coordinates recognition, pure route rules and output adapters. It has
no dependency on argument parsing or Tk, so both entry points use the same flow.
"""
from datetime import datetime
from pathlib import Path
import tempfile
from .errors import RecognitionError
from .image_io import read_image, write_image
from .recognize import CONFIG_VERSION, recognize
from .domain.solver import solve
from .domain.geometry import export_solution
from .artifacts import write_analysis_artifacts, write_error_artifact, write_result


def run_image(source, destination, limit=20, region=None, *, avoid_repeated=False, excluded_types=(), fallback_priority='stage'):
    destination.mkdir(parents=True,exist_ok=True)
    result = {'input': str(source.resolve()), 'config_version': CONFIG_VERSION,
              'coordinate_system': '1-based [row,column]',
              'assumptions': {'revisit':False,'horizontal_in_first_and_last_rows':True}}
    try:
        input_image=read_image(source)
        offset=(0,0)
        if region is not None:
            if len(region)!=4 or any(not isinstance(v,int) for v in region):
                raise RecognitionError([{'code':'INVALID_REGION','message':'Region must contain four integer coordinates.'}])
            x1,y1,x2,y2=region
            h,w=input_image.shape[:2]
            if not (0<=x1<x2<=w and 0<=y1<y2<=h and x2-x1>=20 and y2-y1>=20):
                raise RecognitionError([{'code':'INVALID_REGION','message':'Region is empty, too small or outside the input image.'}])
            input_image=input_image[y1:y2,x1:x2].copy()
            offset=(x1,y1)
            result['input_region']=list(region)
            write_image(destination/'input.png',input_image)
        board, origin, edges, diagnostics, score = recognize(input_image)
        origin=(origin[0]+offset[0],origin[1]+offset[1])
        from .contents import CONTENT_NAMES, classify_contents
        excluded_types = tuple(excluded_types)
        if any(key not in CONTENT_NAMES for key in excluded_types):
            raise ValueError('Unknown excluded content type')
        filtered = bool(avoid_repeated or excluded_types)
        labels, content_diagnostics = classify_contents(board, strict=filtered)
        result['content_types'] = [[labels[r,c] for c in range(5)] for r in range(10)]
        result['content_diagnostics'] = content_diagnostics
        if filtered:
            result['filters'] = {'avoid_repeated':avoid_repeated, 'excluded_types':list(excluded_types)}
        solved = solve([(r,c) for r in range(10) for c in range(5)],edges,limit,
                       node_types=labels, excluded_types=excluded_types, avoid_repeated=avoid_repeated, fallback_priority=fallback_priority)
        result.update(export_solution(solved))
        result['board_origin'] = origin
        result['board_match'] = score
        write_analysis_artifacts(destination, board, edges, diagnostics, solved)
    except RecognitionError as exc:
        result.update(status='error', errors=exc.issues)
        write_error_artifact(destination, exc)
    write_result(destination, result)
    return result


def analyze_file(source, output_root, limit=20, region=None, on_created=None, *, avoid_repeated=False, excluded_types=(), fallback_priority='stage'):
    """Run analysis into a newly allocated folder; no earlier result is overwritten."""
    source, output_root = Path(source), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = datetime.now().strftime('%Y%m%d_%H%M%S_')
    destination = Path(tempfile.mkdtemp(prefix=prefix, dir=output_root))
    if on_created is not None:
        on_created(destination)
    result = run_image(source, destination, limit=limit, region=region,
                       avoid_repeated=avoid_repeated, excluded_types=excluded_types, fallback_priority=fallback_priority)
    name = 'error.png' if result['status'] == 'error' else ('board.png' if result['status'] in ('ok','partial') else 'route.png')
    preview = destination / name
    if not preview.is_file():
        preview = destination/'input.png' if (destination/'input.png').is_file() else source
    try:
        image = read_image(preview)
    except RecognitionError:
        image = None
    return result, destination, image
