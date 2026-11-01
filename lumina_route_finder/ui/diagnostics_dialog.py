"""Asynchronous, cancellable comparison; applying a proposal is explicit."""
import base64
from copy import deepcopy
import queue
import threading
import tkinter as tk
from tkinter import ttk,messagebox
import cv2
from ..domain.diagnostics import diagnose,compare_relaxations
from ..domain.jobs import AnalysisCancelled
from ..domain.catalog import CONTENT_NAMES
from ..diagnostic_render import render_diagnostics

class DiagnosticsDialog:
    def __init__(self,app):
        self.app=app;self.key=app.analysis_cache.key;self.revision=app.analysis_cache.revision;self.snapshot=deepcopy(app.analysis_cache.snapshot);self.options=app.current_search()
        self.closed=False;self.cancel=threading.Event();self.messages=queue.Queue();self.rows=[];self.poll_id=None
        self.window=tk.Toplevel(app.root);self.window.title('未到達の原因・条件緩和の比較');self.window.geometry('1100x850');self.window.transient(app.root)
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.bind('<Destroy>',lambda e:self.on_destroy() if e.widget==self.window else None)
        body=ttk.Panedwindow(self.window,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=12)
        left=ttk.Frame(body);right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=1)
        ttk.Label(left,text='緑: 到達可能 / 赤: 除外・通行不可 / 黄: 最深段 / 灰: 到達不可',wraplength=450).pack(anchor='w')
        self.canvas=tk.Canvas(left,bg='#e6ebf1');self.canvas.pack(fill='both',expand=True);self.canvas.bind('<Configure>',lambda e:self.draw())
        self.diagnostic=diagnose(self.snapshot.labels,self.snapshot.edges,self.snapshot.labels,self.options)
        stage=self.diagnostic['furthest_stage'];goal=self.diagnostic['goal_stage']
        text='現在の条件でゴールへ到達できます。' if self.diagnostic['goal_reachable'] else (f'到達可能な最深段は第{stage}段階です。' if stage else '起点がすべて除外されています。')
        if self.diagnostic['frontier_edges']:text+='\n到達範囲から先へ進む接続に、除外・連続禁止による制限があります。'
        else:
            if stage<goal:text+='\n接続データ上、これ以上先の段階へ進めません。'
        ttk.Label(right,text=text,wraplength=480).pack(anchor='w',pady=8)
        ttk.Label(right,text='条件を緩めた結果（自動適用しません）').pack(anchor='w')
        columns=('条件','結果','段階','通過数','重み')
        tableframe=ttk.Frame(right);tableframe.pack(fill='both',expand=True)
        self.table=ttk.Treeview(tableframe,columns=columns,show='headings',selectmode='browse')
        for column,width in zip(columns,(180,75,50,60,70)):self.table.heading(column,text=column);self.table.column(column,width=width,stretch=True)
        scroll=ttk.Scrollbar(tableframe,orient='vertical',command=self.table.yview);self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.status=ttk.Label(right,text='比較中…',wraplength=480);self.status.pack(anchor='w',pady=8)
        self.apply_button=ttk.Button(right,text='選択条件を適用して再探索',command=self.apply,state='disabled');self.apply_button.pack(anchor='w',pady=6)
        ttk.Button(right,text='比較を中止',command=self.cancel.set).pack(anchor='w',pady=6)
        self.draw();threading.Thread(target=self.worker,daemon=True).start();self.poll_id=self.window.after(50,self.poll)
    def worker(self):
        try:
            result=compare_relaxations(self.snapshot.labels,self.snapshot.edges,self.snapshot.labels,self.options,self.cancel,
                                       progress=lambda name:self.messages.put(('progress',name)))
            self.messages.put(('done',result))
        except AnalysisCancelled:self.messages.put(('cancelled',None))
        except Exception as exc:self.messages.put(('error',str(exc)))
    def poll(self):
        if self.closed:return
        try:kind,payload=self.messages.get_nowait()
        except queue.Empty:kind=None
        if kind=='progress':self.status.configure(text='比較中: '+self.name(payload))
        elif kind=='done':
            if self.cancel.is_set():
                self.status.configure(text='比較を中止しました。');self.poll_id=None;return
            self.rows=payload
            for i,row in enumerate(payload):
                r=row['result'];state={'ok':'到達','partial':'未到達','no_path':'経路なし','error':'種類未確定'}.get(r['status'],r['status'])
                weight=r.get('path_weights',[None])[0]
                self.table.insert('','end',iid=str(i),values=(self.name(row['name']),state,r.get('reached_stage',0),r.get('max_count') or 0,'—' if weight is None else f'{weight:g}'))
            self.status.configure(text='比較完了。評価方法・重みは維持し、表示した条件だけを緩めています。')
            self.apply_button.configure(state='normal');self.poll_id=None;return
        elif kind in ('cancelled','error'):
            self.status.configure(text='比較を中止しました。' if kind=='cancelled' else '比較できませんでした: '+payload);self.poll_id=None;return
        self.poll_id=self.window.after(40,self.poll)
    def name(self,text):
        return '除外解除: '+CONTENT_NAMES.get(text.split(': ',1)[1],text) if text.startswith('除外解除: ') else text
    def draw(self):
        if not hasattr(self,'diagnostic') or self.closed:return
        image=render_diagnostics(self.snapshot.board,self.diagnostic);h,w=image.shape[:2]
        scale=min(max(1,self.canvas.winfo_width()-12)/w,max(1,self.canvas.winfo_height()-12)/h)
        image=cv2.resize(image,(max(1,int(w*scale)),max(1,int(h*scale))))
        _,data=cv2.imencode('.png',image);self.photo=tk.PhotoImage(master=self.canvas,data=base64.b64encode(data).decode())
        self.canvas.delete('all');self.canvas.create_image(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,image=self.photo)
    def apply(self):
        if self.app.busy or self.app.closing or not self.table.selection():return
        try:
            stale=self.app.analysis_cache.key!=self.key or self.app.analysis_cache.revision!=self.revision or self.app.analysis_cache.signature(self.app.view.path.get().strip().strip(chr(34)).strip(chr(39)),self.app.region)!=self.key
        except OSError:stale=True
        if stale:
            messagebox.showerror('比較結果が古くなりました','画像や範囲を変更したため比較し直してください。',parent=self.window);return
        row=self.rows[int(self.table.selection()[0])]
        if row['result']['status']=='error':
            messagebox.showerror('適用できません',row['result']['message'],parent=self.window);return
        self.app.apply_search(row['options']);self.app.start();self.close()
    def on_destroy(self):
        self.closed=True;self.cancel.set()
        if self.poll_id is not None:
            try:self.window.after_cancel(self.poll_id)
            except tk.TclError:pass
            self.poll_id=None
    def close(self):self.on_destroy();self.window.destroy()
