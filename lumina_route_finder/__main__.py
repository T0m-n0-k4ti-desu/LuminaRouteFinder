"""Command line interface. All reported node coordinates are 1-based."""
import argparse
import json
from pathlib import Path
import sys
import cv2
from .recognize import RecognitionError, CONFIG_VERSION, center, read_image, recognize
from .solver import solve


def write_image(path, image):
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise OSError(f'Cannot encode {path}')
    data.tofile(str(path))


def export_solution(result):
    result = dict(result)
    result['paths'] = [[[r+1,c+1] for r,c in path] for path in result['paths']]
    return result


def run_image(source, destination, limit=20):
    destination.mkdir(parents=True,exist_ok=True)
    result = {'input': str(source.resolve()), 'config_version': CONFIG_VERSION,
              'coordinate_system': '1-based [row,column]',
              'assumptions': {'revisit':False,'horizontal_in_first_and_last_rows':True}}
    try:
        board, origin, edges, diagnostics, score = recognize(read_image(source))
        solved = solve([(r,c) for r in range(10) for c in range(5)],edges,limit)
        result.update(export_solution(solved))
        result['board_origin'] = origin
        result['header_match'] = score
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
        if solved['paths']:
            path=solved['paths'][0]
            for u,v in zip(path,path[1:]):
                a=tuple(2*x for x in center(u)); b=tuple(2*x for x in center(v))
                cv2.arrowedLine(display,a,b,(0,60,255),2,cv2.LINE_AA,tipLength=.18)
            for i,n in enumerate(path,1):
                x,y=center(n)
                cv2.circle(display,(2*x,2*y),10,(255,255,255),-1)
                cv2.putText(display,str(i),(2*x-9,2*y+5),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,0),1,cv2.LINE_AA)
        write_image(destination/'route.png',display)
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
    parser.add_argument('--graph',action='store_true',help='Solve a hand-authored JSON graph with 1-based nodes/edges.')
    args=parser.parse_args(argv)
    if args.max_paths < 1:
        parser.error('--max-paths must be positive')
    if args.graph:
        try:
            data=json.loads(args.input.read_text(encoding='utf-8-sig'))
            nodes=[(r-1,c-1) for r,c in data['nodes']]
            edges=[(tuple(x-1 for x in e['from']),tuple(x-1 for x in e['to'])) for e in data['edges']]
            result=export_solution(solve(nodes,edges,args.max_paths))
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
        result=run_image(source,target,args.max_paths)
        status=result['status']
        details=result.get('max_count') if status=='ok' else [x['code'] for x in result.get('errors',[])]
        print(f'{source.name}: {status} {details}',flush=True)
        statuses.append(status)
    return 0 if all(s=='ok' for s in statuses) else 1


if __name__=='__main__':
    sys.exit(main())
