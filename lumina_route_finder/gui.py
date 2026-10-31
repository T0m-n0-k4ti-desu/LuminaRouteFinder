"""Desktop GUI: file selection/drop, asynchronous analysis and result preview."""
import argparse
import base64
from datetime import datetime
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import cv2
from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

from .__main__ import run_image
from .recognize import RecognitionError, read_image
from .render import render_route

ERROR_MESSAGES = {
    'INPUT_READ_ERROR': '画像を読み込めません。ファイルが存在し、対応する画像形式か確認してください。',
    'BOARD_NOT_FOUND': '盤面を検出できません。5列・全10段階のアイコンと接続線が残る画像を指定してください。強く縮小された画像は元の画質で撮影し直してください。',
    'MULTIPLE_BOARDS': '盤面ウィンドウが複数あります。対象を1つにして撮影してください。',
    'UNSUPPORTED_LAYOUT': 'この画面配置・倍率には対応していません。強い縦横の変形を避け、十分な大きさで撮影してください。',
    'INCOMPLETE_BOARD': '下の段のアイコンが選択され、上側の経路が非表示です。選択を解除し、全経路が見える状態で撮影してください。',
    'CURSOR_OCCLUSION': 'ゲーム内カーソルが盤面に重なっています。カーソルを盤面外に移動して撮影してください。',
    'AMBIGUOUS_CONNECTION': '接続線を確定できません。遮蔽や画像の劣化を確認し、撮影し直してください。',
    'INVALID_BOARD_STRUCTURE': 'アイコンの配置・輪郭を確認できません。盤面全体が遮られずに写っているか確認してください。',
}


def describe_result(result, page=0):
    """Return a user-facing title, details and whether this is a success."""
    if result['status'] == 'ok':
        count = result['max_count']
        total = result['optimal_path_count']
        path = result['paths'][page]
        details = f'同率の最長経路: {total}通り\n候補 {page+1}/{len(result["paths"])} を表示しています。\n\n通過順（段階・列）\n'
        details += '\n'.join(f'{i:2}. 第{r}段階・{c}列目' for i, (r,c) in enumerate(path,1))
        return f'解析完了 · 最大{count}アイコン', details, True
    if result['status'] == 'no_path':
        return 'ゴールに到達できません', '認識した接続では第1段階から第10段階への経路がありません。接続確認画像 recognized.png も確認してください。', False
    messages = []
    for error in result.get('errors', []):
        code = error['code']
        message = ERROR_MESSAGES.get(code, error.get('message', '不明なエラーです。'))
        text = f'{message}\n[{code}]'
        if text not in messages:
            messages.append(text)
    return '解析できませんでした', '\n\n'.join(messages), False


def analyze_file(source, output_root, limit=20):
    """Run analysis into a newly allocated folder; no earlier result is overwritten."""
    source, output_root = Path(source), Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    prefix = datetime.now().strftime('%Y%m%d_%H%M%S_')
    destination = Path(tempfile.mkdtemp(prefix=prefix, dir=output_root))
    result = run_image(source, destination, limit=limit)
    name = 'error.png' if result['status'] == 'error' else ('board.png' if result['status'] == 'ok' else 'route.png')
    preview = destination / name
    if not preview.is_file():
        preview = source  # e.g. the window could not be located: show the input.
    try:
        image = read_image(preview)
    except RecognitionError:
        image = None
    return result, destination, image


class Application:
    def __init__(self, root, output_root=Path('outputs/gui')):
        self.root = root
        self.output_root = Path(output_root)
        self.result = None
        self.board = None
        self.page = 0
        self.page_limit = 20
        self.requested_page = 0
        self.busy = False
        self.closed = False
        self.messages = queue.Queue()
        self.image = None
        self.photo = None
        self.zoom = None  # None = fit to canvas
        self.destination = None
        self.poll_id = None
        self.resize_id = None
        root.title('LuminaRouteFinder — 最大経路検索')
        root.geometry('1100x840')
        root.minsize(850, 620)
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        style.configure('Title.TLabel', font=('Yu Gothic UI', 18, 'bold'))
        style.configure('Status.TLabel', font=('Yu Gothic UI', 12, 'bold'))
        main = ttk.Frame(root, padding=18)
        main.pack(fill='both', expand=True)
        ttk.Label(main,text='LuminaRouteFinder',style='Title.TLabel').pack(anchor='w')
        ttk.Label(main,text='画像を指定して、第1段階から第10段階の最大経路を検索').pack(anchor='w',pady=(2,14))
        inputs = ttk.Frame(main)
        inputs.pack(fill='x')
        self.path = tk.StringVar()
        self.entry = ttk.Entry(inputs,textvariable=self.path)
        self.entry.pack(side='left',fill='x',expand=True)
        self.browse_button = ttk.Button(inputs,text='画像を選択…',command=self.browse)
        self.browse_button.pack(side='left',padx=8)
        self.analyze_button = ttk.Button(inputs,text='解析',command=self.start)
        self.analyze_button.pack(side='left')
        self.drop_label = tk.Label(main,text='画像ファイルをここにドラッグ＆ドロップできます（1枚）',
                                   bg='#eef3f8',fg='#42556b',pady=12,highlightthickness=1,highlightbackground='#b8c9da')
        self.drop_label.pack(fill='x',pady=(10,12))
        self.progress = ttk.Progressbar(main,mode='indeterminate')
        body = ttk.Frame(main)
        self.body = body
        body.pack(fill='both',expand=True)
        body.columnconfigure(0,weight=1)
        body.columnconfigure(1,weight=0)
        body.rowconfigure(0,weight=1)
        preview_frame = ttk.Frame(body)
        preview_frame.grid(row=0,column=0,sticky='nsew',padx=(0,16))
        preview_frame.columnconfigure(0,weight=1)
        preview_frame.rowconfigure(0,weight=1)
        self.canvas = tk.Canvas(preview_frame,bg='#e6ebf1',highlightthickness=0)
        self.canvas.grid(row=0,column=0,sticky='nsew')
        vertical = ttk.Scrollbar(preview_frame,orient='vertical',command=self.canvas.yview)
        vertical.grid(row=0,column=1,sticky='ns')
        horizontal = ttk.Scrollbar(preview_frame,orient='horizontal',command=self.canvas.xview)
        horizontal.grid(row=1,column=0,sticky='ew')
        self.canvas.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.canvas.bind('<Configure>',self.schedule_render)
        toolbar = ttk.Frame(preview_frame)
        toolbar.grid(row=2,column=0,sticky='w',pady=(8,0))
        ttk.Button(toolbar,text='全体表示',command=self.fit).pack(side='left')
        ttk.Button(toolbar,text='＋',width=4,command=lambda:self.change_zoom(1.25)).pack(side='left',padx=4)
        ttk.Button(toolbar,text='－',width=4,command=lambda:self.change_zoom(.8)).pack(side='left')
        self.scale_text = tk.StringVar(value='')
        ttk.Label(toolbar,textvariable=self.scale_text).pack(side='left',padx=10)
        self.pages = ttk.Frame(preview_frame)
        self.pages.grid(row=3,column=0,sticky='ew',pady=(10,0))
        self.previous_button = ttk.Button(self.pages,text='← 前へ',command=lambda:self.change_page(-1),state='disabled')
        self.previous_button.pack(side='left')
        self.page_text = tk.StringVar(value='')
        ttk.Label(self.pages,textvariable=self.page_text).pack(side='left',padx=12)
        self.next_button = ttk.Button(self.pages,text='次へ →',command=lambda:self.change_page(1),state='disabled')
        self.next_button.pack(side='left')
        sidebar = ttk.Frame(body,width=310)
        sidebar.grid(row=0,column=1,sticky='nsew')
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0,weight=1)
        sidebar.rowconfigure(1,weight=1)
        self.status = ttk.Label(sidebar,text='画像を指定してください',style='Status.TLabel',wraplength=300)
        self.status.grid(row=0,column=0,sticky='ew',pady=(0,12))
        self.details = tk.Text(sidebar,width=30,wrap='word',font=('Yu Gothic UI',10),
                               bg='#f7f9fc',relief='flat',padx=10,pady=10,state='disabled')
        self.details.grid(row=1,column=0,sticky='nsew')
        self.open_button = ttk.Button(sidebar,text='結果フォルダーを開く',command=self.open_output,state='disabled')
        self.open_button.grid(row=2,column=0,sticky='ew',pady=(12,0))
        self.output_label = ttk.Label(sidebar,text='',wraplength=300)
        self.output_label.grid(row=3,column=0,sticky='ew',pady=(8,0))
        for widget in (self.entry,self.drop_label,self.canvas):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>',self.on_drop)
        self.path.trace_add('write',self.path_changed)
        self.entry.bind('<Return>',lambda event:self.start())
        self.set_details('パスを入力するか、画像を選択・ドロップして「解析」を押してください。\n\n対応形式: JPG / PNG / BMP\n\n結果の番号はアイコンの通過順です。')
        self.render()
        self.poll_id = root.after(80,self.poll)

    def set_details(self,text):
        self.details.configure(state='normal')
        self.details.delete('1.0','end')
        self.details.insert('1.0',text)
        self.details.configure(state='disabled')

    def clear_result(self):
        self.result = self.board = None
        self.page = 0
        self.page_text.set('')
        self.previous_button.configure(state='disabled')
        self.next_button.configure(state='disabled')
        self.image = self.photo = None
        self.zoom = None
        self.destination = None
        self.open_button.configure(state='disabled')
        self.output_label.configure(text='')
        self.render()

    def path_changed(self,*_):
        if self.busy:
            return
        self.clear_result()
        self.status.configure(text='解析の準備ができました' if self.path.get().strip() else '画像を指定してください',foreground='#26374a')
        self.set_details('「解析」を押してください。')

    def browse(self):
        selected = filedialog.askopenfilename(parent=self.root,title='解析する画像を選択',
            filetypes=[('画像ファイル','*.jpg *.jpeg *.png *.bmp'),('すべてのファイル','*.*')])
        if selected:
            self.path.set(selected)

    def on_drop(self,event):
        if self.busy:
            return 'refuse_drop'
        try:
            paths = self.root.tk.splitlist(event.data)
        except tk.TclError:
            paths = ()
        if len(paths) != 1:
            self.show_error('画像を1枚だけドロップしてください。')
            return 'refuse_drop'
        self.path.set(paths[0])
        return COPY

    def show_error(self,message):
        self.clear_result()
        self.status.configure(text='解析できませんでした',foreground='#b42318')
        self.set_details(message)

    def start(self, limit=20, selected_page=0):
        if self.busy:
            return
        value = self.path.get().strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):
            value = value[1:-1]
        source = Path(value).expanduser()
        if not value or not source.is_file():
            self.show_error('存在する画像ファイルを指定してください。フォルダーは指定できません。')
            return
        self.clear_result()
        self.page_limit = limit
        self.requested_page = selected_page
        self.busy = True
        self.entry.configure(state='disabled')
        self.browse_button.configure(state='disabled')
        self.analyze_button.configure(state='disabled')
        self.status.configure(text='解析中…',foreground='#26374a')
        self.set_details('盤面と接続を確認しています。')
        self.progress.pack(fill='x',pady=(0,10),before=self.body)
        self.progress.start(12)
        threading.Thread(target=self.worker,args=(source.resolve(),limit),daemon=True).start()

    def worker(self,source,limit):
        try:
            self.messages.put(('done',analyze_file(source,self.output_root,limit)))
        except Exception as exc:
            self.messages.put(('failed',str(exc)))

    def poll(self):
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.closed:
            return
        try:
            kind,payload = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            self.progress.pack_forget()
            for widget in (self.entry,self.browse_button,self.analyze_button):
                widget.configure(state='normal')
            if kind == 'failed':
                self.show_error('解析処理を完了できませんでした。\n\n'+payload)
            else:
                result,self.destination,self.image = payload
                self.result = result
                title,details,success = describe_result(result)
                self.status.configure(text=title,foreground='#147447' if success else '#b42318')
                self.set_details(details)
                self.output_label.configure(text=f'保存先:\n{self.destination.resolve()}')
                self.open_button.configure(state='normal')
                if success:
                    self.board = self.image
                    self.show_page(min(self.requested_page,len(result['paths'])-1))
                else:
                    self.render()
        self.poll_id = self.root.after(80,self.poll)

    def show_page(self, page):
        if self.result is None or self.result['status'] != 'ok':
            return
        self.page = page
        paths = self.result['paths']
        path = [(r-1,c-1) for r,c in paths[page]]
        self.image = render_route(self.board,path)
        _,details,_ = describe_result(self.result,page)
        self.set_details(details)
        total = self.result['optimal_path_count']
        self.page_text.set(f'候補 {page+1} / {total}')
        self.previous_button.configure(state='normal' if page else 'disabled')
        more = page+1 < len(paths) or self.result.get('paths_truncated',False)
        self.next_button.configure(state='normal' if more else 'disabled')
        self.render()

    def change_page(self, delta):
        if self.busy or self.result is None or self.result['status'] != 'ok':
            return
        page = self.page + delta
        if 0 <= page < len(self.result['paths']):
            self.show_page(page)
        elif page == len(self.result['paths']) and self.result.get('paths_truncated',False):
            # Fetch additional optimal paths only when needed; retain the exact total.
            self.start(limit=self.page_limit*2,selected_page=page)

    def schedule_render(self,event=None):
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
        self.resize_id = self.root.after(80,self.render)

    def render(self):
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
        self.resize_id = None
        if self.closed:
            return
        self.canvas.delete('all')
        width,height=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        if self.image is None:
            self.scale_text.set('')
            self.canvas.configure(scrollregion=(0,0,width,height))
            self.canvas.create_text(width/2,height/2,text='解析結果の画像をここに表示します',fill='#65768b',width=max(100,width-40))
            return
        ih,iw=self.image.shape[:2]
        fit=min(max(1,width-20)/iw,max(1,height-20)/ih)
        scale=fit if self.zoom is None else self.zoom
        self.display_scale=scale
        resized=cv2.resize(self.image,(max(1,round(iw*scale)),max(1,round(ih*scale))),
                           interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_NEAREST)
        ok,png=cv2.imencode('.png',resized)
        if not ok:
            return
        self.photo=tk.PhotoImage(master=self.root,data=base64.b64encode(png).decode('ascii'))
        dw,dh=resized.shape[1],resized.shape[0]
        self.canvas.create_image(max(width,dw)/2,max(height,dh)/2,image=self.photo)
        self.canvas.configure(scrollregion=(0,0,max(width,dw),max(height,dh)))
        self.scale_text.set(f'{scale:.0%}')

    def fit(self):
        self.zoom=None
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.render()

    def change_zoom(self,factor):
        if self.image is not None:
            self.zoom=max(.1,min(4,getattr(self,'display_scale',1)*factor))
            self.render()

    def open_output(self):
        if self.destination is None:
            return
        try:
            path=str(self.destination.resolve())
            if sys.platform == 'win32':
                os.startfile(path)
            else:
                subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',path])
        except OSError as exc:
            self.set_details(f'フォルダーを開けませんでした。\n{self.destination}\n\n{exc}')

    def close(self):
        self.closed=True
        for callback in (self.poll_id,self.resize_id):
            if callback is not None:
                self.root.after_cancel(callback)
        self.root.destroy()


def main(argv=None):
    parser=argparse.ArgumentParser(description='LuminaRouteFinder GUI')
    parser.add_argument('image',nargs='?',type=Path,help='起動時に指定する画像')
    parser.add_argument('--output-dir',type=Path,default=Path('outputs/gui'))
    args=parser.parse_args(argv)
    root=TkinterDnD.Tk()
    app=Application(root,args.output_dir)
    if args.image:
        app.path.set(str(args.image))
    root.mainloop()


if __name__ == '__main__':
    main()
