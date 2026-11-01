"""Command line interface. All reported node coordinates are 1-based."""
import argparse
import json
from pathlib import Path
import sys
import cv2
from .recognize import RecognitionError, CONFIG_VERSION, center, read_image, recognize
from .solver import solve
from .render import render_route


def write_image(path, image):
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise OSError(f'Cannot encode {path}')
    data.tofile(str(path))


def export_solution(result):
    result = dict(result)
    result['paths'] = [[[r+1,c+1] for r,c in path] for path in result['paths']]
    return result


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
        graph = {'nodes': [[r+1,c+1] for r in range(10) for c in range(5)],
                 'edges': [{'from':[u[0]+1,u[1]+1], 'to':[v[0]+1,v[1]+1]} for u,v in edges],
                 'diagnostics': [{**d,'from':[d['from'][0]+1,d['from'][1]+1],
                                  'to':[d['to'][0]+1,d['to'][1]+1]} for d in diagnostics]}
        (destination/'board.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
        display = cv2.resize(board,None,fx=2,fy=2,interpolation=cv2.INTER_NEAREST)
        recognized = display.copy()
        for u,v in edges:
            a=tuple(2*x for x in center(u)); b=tuple(2*x for x in center(v))
            cv2.line(recognized,a,b,(0,0,255),1,cv2.LINE_AA)
        write_image(destination/'recognized.png',recognized)
        write_image(destination/'board.png',board)
        path = solved['paths'][0] if solved['paths'] else []
        write_image(destination/'route.png',render_route(board,path))
    except RecognitionError as exc:
        result.update(status='error', errors=exc.issues)
        if exc.board is not None:
            display=exc.board.copy()
            for item in exc.issues:
                if 'board_box' in item:
                    x,y,w,h=item['board_box']
                    cv2.rectangle(display,(x,y),(x+w,y+h),(0,0,255),2)
            write_image(destination/'error.png',cv2.resize(display,None,fx=2,fy=2))
    (destination/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


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
        result=run_image(source,target,args.max_paths,fallback_priority=None if args.fallback_priority=='none' else args.fallback_priority)
        status=result['status']
        details=result.get('max_count') if status in ('ok','partial') else [x['code'] for x in result.get('errors',[])]
        print(f'{source.name}: {status} {details}',flush=True)
        statuses.append(status)
    return 0 if all(s=='ok' for s in statuses) else 1


if __name__=='__main__':
    sys.exit(main())
