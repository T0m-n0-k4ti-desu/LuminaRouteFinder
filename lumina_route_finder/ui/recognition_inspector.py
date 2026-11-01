"""Recognition viewer with explicit edge/type correction and undo."""
import base64
import tkinter as tk
from tkinter import ttk,messagebox
import cv2
from ..application.review import RecognitionEditor
from ..rendering.recognition import render_recognition
from ..domain.catalog import CONTENT_NAMES
from ..domain.geometry import candidates

class RecognitionInspector:
    def __init__(self,app):
        self.app=app;self.key=app.analysis_cache.key;self.revision=app.analysis_cache.revision
        self.editor=RecognitionEditor(app.analysis_cache.snapshot,app.analysis_cache.original)
        self.node=None;self.edge=None
        self.window=tk.Toplevel(app.root);self.window.title('認識確認・手動補正');self.window.geometry('1100x850');self.window.transient(app.root)
        ttk.Label(self.window,text='緑＝接続あり / 橙＝未確定・種類不明 / 青＝選択。補正は「確認して再探索」で適用します。').pack(anchor='w',padx=12,pady=8)
        body=ttk.Panedwindow(self.window,orient='horizontal');body.pack(fill='both',expand=True,padx=12)
        left=ttk.Frame(body);right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=1)
        self.canvas=tk.Canvas(left,bg='#e6ebf1');self.canvas.pack(fill='both',expand=True);self.canvas.bind('<Configure>',lambda e:self.draw())
        tabs=ttk.Notebook(right);tabs.pack(fill='both',expand=True)
        nodes=ttk.Frame(tabs);edges=ttk.Frame(tabs);tabs.add(nodes,text='アイコン種類');tabs.add(edges,text='接続')
        self.nodes=self.tree(nodes,('位置','種類','一致度','差'))
        self.kind=tk.StringVar();self.kind_values={'不明':None,**{v:k for k,v in CONTENT_NAMES.items()}}
        ttk.Combobox(nodes,textvariable=self.kind,values=list(self.kind_values),state='readonly').pack(fill='x',pady=5)
        ttk.Button(nodes,text='選択アイコンの種類を変更',command=self.change_kind).pack(anchor='w')
        self.edges=self.tree(edges,('始点→終点','状態','画素数'))
        self.edge_state=tk.StringVar(value='なし')
        ttk.Combobox(edges,textvariable=self.edge_state,values=['あり','なし'],state='readonly').pack(fill='x',pady=5)
        ttk.Button(edges,text='選択接続を確認・変更',command=self.change_edge).pack(anchor='w')
        self.nodes.bind('<<TreeviewSelect>>',self.node_selected);self.edges.bind('<<TreeviewSelect>>',self.edge_selected)
        footer=ttk.Frame(self.window,padding=12);footer.pack(fill='x')
        self.gaps=tk.BooleanVar()
        ttk.Checkbutton(footer,text='接続のない段間も画像で確認しました',variable=self.gaps).pack(anchor='w')
        self.notice=ttk.Label(footer,text='',wraplength=1000);self.notice.pack(anchor='w',pady=5)
        for text,command in [('元の自動判定へ戻す',self.reset),('1つ戻す',self.undo),('確認して再探索',self.apply),('閉じる',self.window.destroy)]:ttk.Button(footer,text=text,command=command).pack(side='left',padx=4)
        self.refresh()
    def tree(self,parent,columns):
        frame=ttk.Frame(parent);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=columns,show='headings',selectmode='browse')
        for column in columns:tree.heading(column,text=column);tree.column(column,width=110,stretch=True)
        scroll=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        return tree
    def refresh(self):
        snapshot=self.editor.snapshot;self.nodes.delete(*self.nodes.get_children());self.edges.delete(*self.edges.get_children())
        content={tuple(d['node']):d for d in snapshot.content_diagnostics}
        for node,kind in sorted(snapshot.labels.items()):
            r,c=node;d=content.get((r+1,c+1),{})
            self.nodes.insert('', 'end',iid=f'{r},{c}',values=(f'{r+1}-{c+1}',CONTENT_NAMES.get(kind,'不明'),f"{d.get('score',0):.2f}",f"{d.get('margin',0):.2f}"))
        diagnostics={(tuple(d['from']),tuple(d['to'])):d for d in snapshot.diagnostics}
        for index,(u,v) in enumerate(candidates()):
            d=diagnostics.get((u,v),{});state='未確認' if (u,v) in snapshot.pending_edges else ('あり' if (u,v) in snapshot.edges else 'なし')
            self.edges.insert('','end',iid=str(index),values=(f'{u[0]+1}-{u[1]+1} → {v[0]+1}-{v[1]+1}',state,d.get('dark_pixels','—')))
        gaps=self.editor.missing_rows()
        self.notice.configure(text=f'手動操作 {len(snapshot.corrections)}件 / 未確認接続 {len(snapshot.pending_edges)}件 / 接続のない段間: '+(', '.join(str(r)+'→'+str(r+1) for r in gaps) or 'なし'))
        self.draw()
    def draw(self):
        if not self.canvas.winfo_exists():return
        image=render_recognition(self.editor.snapshot,self.node,self.edge)
        h,w=image.shape[:2];scale=min(max(1,self.canvas.winfo_width()-12)/w,max(1,self.canvas.winfo_height()-12)/h)
        image=cv2.resize(image,(max(1,int(w*scale)),max(1,int(h*scale))))
        _,data=cv2.imencode('.png',image);self.photo=tk.PhotoImage(master=self.canvas,data=base64.b64encode(data).decode())
        self.canvas.delete('all');self.canvas.create_image(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,image=self.photo)
    def node_selected(self,event=None):
        if self.nodes.selection():
            self.node=tuple(map(int,self.nodes.selection()[0].split(',')));kind=self.editor.snapshot.labels[self.node]
            self.kind.set(CONTENT_NAMES.get(kind,'不明'));self.edge=None;self.draw()
    def edge_selected(self,event=None):
        if self.edges.selection():
            self.edge=list(candidates())[int(self.edges.selection()[0])];self.node=None
            self.edge_state.set('あり' if self.edge in self.editor.snapshot.edges else 'なし');self.draw()
    def change_kind(self):
        if self.node is not None and self.kind.get() in self.kind_values:
            self.editor.set_label(self.node,self.kind_values[self.kind.get()]);self.refresh()
    def change_edge(self):
        if self.edge is not None:self.gaps.set(False);self.editor.set_edge(*self.edge,self.edge_state.get()=='あり');self.refresh()
    def undo(self):self.editor.undo();self.gaps.set(False);self.refresh()
    def reset(self):self.editor.reset();self.gaps.set(False);self.refresh()
    def apply(self):
        if self.app.busy or self.app.closing:return
        try:
            if self.app.analysis_cache.key!=self.key or self.app.analysis_cache.revision!=self.revision or self.app.analysis_cache.signature(self.app.view.path.get().strip().strip('"').strip("'"),self.app.region)!=self.key:
                raise ValueError('画像・解析範囲が変わりました。現在の画像を解析し直してください。')
            snapshot=self.editor.confirm(self.gaps.get())
        except (OSError,ValueError) as exc:
            messagebox.showerror('補正を適用できません',str(exc),parent=self.window);return
        self.app.analysis_cache.update(snapshot);self.app.options_changed();self.app.start();self.window.destroy()
