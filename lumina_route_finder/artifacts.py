"""Write the stable JSON/PNG analysis artifacts."""
import json
import cv2
from .domain.geometry import center
from .image_io import write_image
from .render import render_route


def write_analysis_artifacts(destination, board, edges, diagnostics, solved):
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


def write_error_artifact(destination, exc):
    if exc.board is not None:
        display=exc.board.copy()
        for item in exc.issues:
            if 'board_box' in item:
                x,y,w,h=item['board_box']
                cv2.rectangle(display,(x,y),(x+w,y+h),(0,0,255),2)
        write_image(destination/'error.png',cv2.resize(display,None,fx=2,fy=2))


def write_result(destination, result):
    (destination/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
