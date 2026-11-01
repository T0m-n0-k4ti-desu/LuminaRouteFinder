"""Command-line arguments and batch dispatch."""
import argparse
import json
import sys
from pathlib import Path
from .analysis import run_image
from ..shared.errors import error_result
from ..shared.messages import format_issues
from ..domain.solver import solve
from ..domain.geometry import export_solution


def main(argv=None):
    parser=argparse.ArgumentParser(description='Find the longest downward icon path in Lumina Corridor.')
    parser.add_argument('input',type=Path)
    parser.add_argument('--output-dir',type=Path,default=Path('outputs'))
    parser.add_argument('--max-paths',type=int,default=20)
    parser.add_argument('--fallback-priority',choices=('stage','count','none'),default='stage',help='If goal is unreachable: prefer reached stage or icon count; none disables fallback.')
    parser.add_argument('--graph',action='store_true',help='Solve a hand-authored JSON graph with 1-based nodes/edges.')
    args=parser.parse_args(argv)
    if args.max_paths < 1:
        parser.error('--max-paths must be positive')
    if args.graph:
        try:
            data=json.loads(args.input.read_text(encoding='utf-8-sig'))
            nodes=[(r-1,c-1) for r,c in data['nodes']]
            edges=[(tuple(x-1 for x in e['from']),tuple(x-1 for x in e['to'])) for e in data['edges']]
            result=export_solution(solve(nodes,edges,args.max_paths,fallback_priority=None if args.fallback_priority=='none' else args.fallback_priority))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            parser.error(str(exc))
        args.output_dir.mkdir(parents=True,exist_ok=True)
        (args.output_dir/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
        return 0 if result['status']=='ok' else 1
    if args.input.is_dir():
        files=sorted(p for p in args.input.rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp'} and p.is_file())
        root=args.input.resolve()
        out=args.output_dir.resolve()
        files=[p for p in files if not p.resolve().is_relative_to(out)]
    else:
        files=[args.input]
        root=args.input.parent.resolve()
    if not files:
        parser.error('No input images found.')
    statuses=[]
    for source in files:
        # Input-relative hierarchy plus filename extension prevents stem collisions.
        relative=source.resolve().relative_to(root)
        target=args.output_dir/relative.parent/relative.name
        if target.exists():
            # A run always has its own directory, never stale outputs from earlier runs.
            suffix=1
            while target.with_name(target.name+f'.{suffix}').exists():
                suffix+=1
            target=target.with_name(target.name+f'.{suffix}')
        try:
            result=run_image(source,target,args.max_paths,fallback_priority=None if args.fallback_priority=='none' else args.fallback_priority)
        except Exception as exc:
            result=error_result(exc)
            print(format_issues(result['errors'],include_code=True,include_detail=True),file=sys.stderr)
        status=result['status']
        details=result.get('max_count') if status in ('ok','partial') else [x['code'] for x in result.get('errors',[])]
        print(f'{source.name}: {status} {details}',flush=True)
        statuses.append(status)
    return 0 if all(s=='ok' for s in statuses) else 1
