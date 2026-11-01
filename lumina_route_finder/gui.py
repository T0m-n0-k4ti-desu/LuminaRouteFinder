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
from tkinter import filedialog, messagebox, ttk

import cv2
from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

from .__main__ import run_image
from .recognize import RecognitionError, read_image
from .render import render_route
from .contents import CONTENT_NAMES
from .session import SessionOutputs,load_cleanup_setting,default_settings_path,migrate_cleanup_setting,read_cleanup_setting,load_settings,save_settings as write_gui_settings

FALLBACK_CHOICES={'到達段階を優先':'stage','通過アイコン数を優先':'count','途中経路を表示しない':'none'}

ERROR_MESSAGES = {
    'AMBIGUOUS_CONTENT': 'コンテンツの種類を確定できません。画像の画質や遮蔽を確認するか、除外オプションをオフにしてください。',
    'INVALID_REGION': '解析範囲が小さすぎるか、画像の外にはみ出しています。全50アイコンと接続線を含む範囲を指定してください。',
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
    if result['status'] in ('ok','partial'):
        count = result['max_count']
        total = result['optimal_path_count']
        path = result['paths'][page]
        details = f'同率の最長経路: {total}通り\n候補 {page+1}/{len(result["paths"])} を表示しています。\n\n通過順（段階・列）\n'
        kinds = result.get('content_types')
        details += '\n'.join(f'{i:2}. 第{r}段階・{c}列目' +
                             ('（'+CONTENT_NAMES[kinds[r-1][c-1]]+'）'
                              if kinds and kinds[r-1][c-1] in CONTENT_NAMES else '')
                             for i, (r,c) in enumerate(path,1))
        details = describe_filters(result) + details
        if result['status']=='partial':
            stage=result['reached_stage']
            priority='到達段階を優先' if result.get('fallback_priority')=='stage' else '通過アイコン数を優先'
            details=f'ゴール未到達 · 第{stage}段階まで\n{priority}で途中経路を表示しています。\n\n'+details
            return f'ゴール未到達 · 第{stage}段階・{count}アイコン',details,True
        return f'解析完了 · 最大{count}アイコン', details, True
    if result['status'] == 'no_path':
        return 'ゴールに到達できません', describe_filters(result)+'現在の接続と探索条件では第1段階から第10段階への経路がありません。条件を緩めるか、接続確認画像 recognized.png を確認してください。', False
    messages = []
    for error in result.get('errors', []):
        code = error['code']
        message = ERROR_MESSAGES.get(code, error.get('message', '不明なエラーです。'))
        text = f'{message}\n[{code}]'
        if text not in messages:
            messages.append(text)
    return '解析できませんでした', '\n\n'.join(messages), False


def describe_filters(result):
    filters = result.get('filters', {})
    lines = []
    if filters.get('avoid_repeated'):
        lines.append('同じコンテンツの連続を禁止')
    if filters.get('excluded_types'):
        lines.append('除外: '+ '、'.join(CONTENT_NAMES[k] for k in filters['excluded_types']))
    return '\n'.join(lines)+'\n\n' if lines else ''


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


class Application:
    def __init__(self, root, output_root=Path('outputs/gui'), settings_path=None):
        self.root = root
        self.output_root = Path(output_root).resolve()
        default_output=(Path.cwd()/'outputs/gui').resolve()
        self.session_outputs=SessionOutputs(self.output_root,self.output_root.parent if self.output_root==default_output else None)
        self.settings_path=Path(settings_path).resolve() if settings_path is not None else default_settings_path()
        legacy=self.output_root/'gui-settings.json'
        self.settings_notice=None
        initial_options=load_settings(self.settings_path if read_cleanup_setting(self.settings_path) is not None else legacy)
        initial_setting=read_cleanup_setting(self.settings_path)
        if initial_setting is None:
            initial_setting=load_cleanup_setting(legacy)
        try:
            migrate_cleanup_setting(self.settings_path,legacy)
            self.session_outputs.prune_empty()
        except OSError as exc:
            self.settings_notice='旧設定を移行できませんでした。保存先の権限を確認してください。\n'+str(exc)
        self.delete_outputs=tk.BooleanVar(master=root,value=initial_setting if self.settings_notice else load_cleanup_setting(self.settings_path))
        self.saved_options=initial_options if self.settings_notice else load_settings(self.settings_path)
        self.initial_path_limit=self.saved_options['initial_path_limit']
        self.worker_thread=None
        self.closing=False
        self.close_wait_id=None
        self.result = None
        self.board = None
        self.page = 0
        self.page_limit = self.initial_path_limit
        self.requested_page = 0
        self.busy = False
        self.closed = False
        self.messages = queue.Queue()
        self.input_image = None
        self.region = None
        self.showing_input = False
        self.drag_start = None
        self.panning = False
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
        self.paste_button = ttk.Button(inputs,text='貼り付け',command=self.paste_image)
        self.paste_button.pack(side='left',padx=(0,8))
        self.analyze_button = ttk.Button(inputs,text='解析',command=self.start)
        self.analyze_button.pack(side='left')
        self.drop_label = tk.Label(main,text='画像をドロップ、またはCtrl＋Vで貼り付けできます（1枚）',
                                   bg='#eef3f8',fg='#42556b',pady=12,highlightthickness=1,highlightbackground='#b8c9da')
        self.drop_label.pack(fill='x',pady=(10,12))
        options = ttk.LabelFrame(main, text='探索オプション', padding=8)
        options.pack(fill='x', pady=(0,10))
        self.avoid_repeated = tk.BooleanVar(master=root,value=self.saved_options['avoid_repeated'])
        self.exclude_enabled = tk.BooleanVar(master=root,value=self.saved_options['exclude_enabled'])
        self.repeat_check = ttk.Checkbutton(options,text='同じコンテンツの連続を禁止',variable=self.avoid_repeated,
                                            command=self.options_changed)
        self.repeat_check.grid(row=0,column=0,sticky='w',padx=(0,20))
        self.exclude_check = ttk.Checkbutton(options,text='指定コンテンツを除外',variable=self.exclude_enabled,
                                             command=self.options_changed)
        self.exclude_check.grid(row=0,column=1,sticky='w')
        self.content_list = tk.Listbox(options,selectmode='multiple',exportselection=False,height=4,width=32)
        for name in CONTENT_NAMES.values():
            self.content_list.insert('end',name)
        for i,key in enumerate(CONTENT_NAMES):
            if key in self.saved_options['excluded_types']:self.content_list.selection_set(i)
        self.content_list.grid(row=1,column=1,sticky='ew',pady=(5,0))
        scroll = ttk.Scrollbar(options,orient='vertical',command=self.content_list.yview)
        scroll.grid(row=1,column=2,sticky='ns',pady=(5,0))
        self.content_list.configure(yscrollcommand=scroll.set,state='normal' if self.exclude_enabled.get() else 'disabled')
        ttk.Label(options,text='除外する種類をクリックして選択・解除できます（複数可）。',wraplength=330).grid(row=1,column=0,sticky='w',padx=(0,20))
        self.content_list.bind('<<ListboxSelect>>',self.options_changed)
        ttk.Label(options,text='ゴール未到達時').grid(row=2,column=0,sticky='w',pady=(8,0))
        initial_choice=next(label for label,key in FALLBACK_CHOICES.items() if key==self.saved_options['fallback_priority'])
        self.fallback_priority=tk.StringVar(master=root,value=initial_choice)
        self.fallback_combo=ttk.Combobox(options,textvariable=self.fallback_priority,values=list(FALLBACK_CHOICES),state='readonly',width=30)
        self.fallback_combo.grid(row=2,column=1,sticky='ew',pady=(8,0))
        self.fallback_combo.bind('<<ComboboxSelected>>',self.options_changed)
        self.progress = ttk.Progressbar(main,mode='indeterminate')
        body = ttk.Frame(main)
        self.body = body
        body.pack(fill='both',expand=True)
        self.cleanup_check=ttk.Checkbutton(main,text='終了時に今回の出力（解析結果・貼り付け画像）を削除',variable=self.delete_outputs,command=self.save_settings)
        self.cleanup_check.pack(anchor='w',pady=(12,0))
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
        self.canvas.bind('<ButtonPress-1>',self.pointer_start)
        self.canvas.bind('<B1-Motion>',self.pointer_drag)
        self.canvas.bind('<ButtonRelease-1>',self.pointer_end)
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
        source_tools=ttk.Frame(preview_frame)
        source_tools.grid(row=4,column=0,sticky='ew',pady=(10,0))
        ttk.Button(source_tools,text='入力画像',command=self.show_input).pack(side='left')
        ttk.Button(source_tools,text='解析結果',command=self.show_result).pack(side='left',padx=5)
        self.selecting=tk.BooleanVar(value=False)
        self.select_button=ttk.Checkbutton(source_tools,text='範囲指定',variable=self.selecting,command=self.begin_selection)
        self.select_button.pack(side='left')
        self.reset_region_button=ttk.Button(source_tools,text='範囲解除',command=self.clear_region)
        self.reset_region_button.pack(side='left',padx=5)
        self.region_text=tk.StringVar(value='自動検出（画像全体）')
        ttk.Label(preview_frame,textvariable=self.region_text).grid(row=5,column=0,sticky='w',pady=(4,0))
        sidebar = ttk.Frame(body,width=310)
        sidebar.grid(row=0,column=1,sticky='nsew')
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0,weight=1)
        sidebar.rowconfigure(1,weight=1)
        self.status = ttk.Label(sidebar,text='画像を指定してください',style='Status.TLabel',wraplength=300)
        self.status.grid(row=0,column=0,sticky='ew',pady=(0,12))
        detail_frame=ttk.Frame(sidebar)
        detail_frame.grid(row=1,column=0,sticky='nsew')
        detail_frame.rowconfigure(0,weight=1)
        detail_frame.columnconfigure(0,weight=1)
        self.details = tk.Text(detail_frame,width=30,wrap='word',font=('Yu Gothic UI',10),
                               bg='#f7f9fc',relief='flat',padx=10,pady=10,state='disabled')
        self.details.grid(row=0,column=0,sticky='nsew')
        self.details_scroll=ttk.Scrollbar(detail_frame,orient='vertical',command=self.details.yview)
        self.details_scroll.grid(row=0,column=1,sticky='ns')
        self.details.configure(yscrollcommand=self.details_scroll.set)
        self.open_button = ttk.Button(sidebar,text='結果フォルダーを開く',command=self.open_output,state='disabled')
        self.open_button.grid(row=2,column=0,sticky='ew',pady=(12,0))
        self.output_label = ttk.Label(sidebar,text='',wraplength=300)
        self.output_label.grid(row=3,column=0,sticky='ew',pady=(8,0))
        for widget in (self.entry,self.drop_label,self.canvas):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>',self.on_drop)
        self.path.trace_add('write',self.path_changed)
        self.entry.bind('<Return>',lambda event:self.start())
        self.root.bind('<Control-v>',self.paste_image)
        self.root.bind('<Control-V>',self.paste_image)
        self.set_details('パスを入力するか、画像を選択・ドロップして「解析」を押してください。\n\n対応形式: JPG / PNG / BMP\n\n結果の番号はアイコンの通過順です。')
        if self.settings_notice:
            self.set_details(self.settings_notice)
        self.render()
        self.poll_id = root.after(80,self.poll)

    def set_details(self,text):
        self.details.configure(state='normal')
        self.details.delete('1.0','end')
        self.details.insert('1.0',text)
        self.details.yview_moveto(0)
        self.details.configure(state='disabled')

    def clear_result(self):
        self.drag_start = None
        self.result = self.board = None
        self.page = 0
        self.page_text.set('')
        self.previous_button.configure(state='disabled')
        self.next_button.configure(state='disabled')
        self.image = self.photo = None
        self.showing_input = False
        self.canvas.configure(cursor='')
        self.zoom = None
        self.destination = None
        self.open_button.configure(state='disabled')
        self.output_label.configure(text='')
        self.render()

    def path_changed(self,*_):
        if self.busy or self.closing:
            return
        self.input_image=None
        self.region=None
        self.selecting.set(False)
        self.region_text.set('自動検出（画像全体）')
        self.clear_result()
        value=self.path.get().strip().strip('"').strip("'")
        try:
            if value and Path(value).expanduser().is_file():
                self.input_image=read_image(Path(value).expanduser())
                self.show_input()
        except RecognitionError:
            pass
        self.status.configure(text='解析の準備ができました' if self.path.get().strip() else '画像を指定してください',foreground='#26374a')
        self.set_details('入力画像を確認してください。必要なら「範囲指定」をオンにして盤面をドラッグで囲み、「解析」を押してください。')

    def browse(self):
        selected = filedialog.askopenfilename(parent=self.root,title='解析する画像を選択',
            filetypes=[('画像ファイル','*.jpg *.jpeg *.png *.bmp'),('すべてのファイル','*.*')])
        if selected:
            self.path.set(selected)

    def paste_image(self,event=None):
        if self.busy or self.closing:
            return 'break'
        try:
            from .clipboard import get_clipboard_image
            image=get_clipboard_image()
            if image is None:
                if event is None:
                    self.show_error('クリップボードに画像がありません。Win＋Shift＋Sで対象ウィンドウをコピーしてから貼り付けてください。')
                return None
            self.load_pasted_image(image)
            return 'break'
        except NotImplementedError as exc:
            self.show_error('この環境ではクリップボード画像を取得できません。Linux / WSLでは、\n'
                            'sudo apt install wl-clipboard xclip\n'
                            'で必要なツールを導入してください。画像をファイルに保存し、参照から開くこともできます。\n\n'+str(exc))
            return 'break'
        except (ImportError,OSError,ValueError) as exc:
            self.show_error('クリップボード画像を読み込めませんでした。コピーし直してください。\n\n'+str(exc))
            return 'break'

    def load_pasted_image(self,image):
        from .clipboard import save_clipboard_image
        path=save_clipboard_image(image,self.output_root)
        self.session_outputs.add_file(path)
        self.path.set(str(path))
        self.input_image=read_image(path)
        self.show_input()
        self.status.configure(text='クリップボード画像を読み込みました',foreground='#26374a')
        self.set_details('画像を確認し、「解析」を押してください。貼り付け画像は保存先のclipboardフォルダーにPNGで保存します。')
        self.render()

    def on_drop(self,event):
        if self.busy or self.closing:
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

    def options_changed(self,event=None):
        if self.busy or self.closing:
            return
        self.content_list.configure(state='normal' if self.exclude_enabled.get() else 'disabled')
        if self.result is not None:
            self.clear_result()
            self.show_input()
            self.status.configure(text='探索条件を変更しました。「解析」を押してください。',foreground='#26374a')
            self.set_details('現在の条件で探索するには「解析」を押してください。')
        self.save_settings()

    def start(self, limit=None, selected_page=0):
        if self.busy or self.closing:
            return
        value = self.path.get().strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):
            value = value[1:-1]
        source = Path(value).expanduser()
        if not value or not source.is_file():
            self.show_error('存在する画像ファイルを指定してください。フォルダーは指定できません。')
            return
        avoid_repeated = self.avoid_repeated.get()
        excluded_types = tuple(list(CONTENT_NAMES)[i] for i in self.content_list.curselection()) if self.exclude_enabled.get() else ()
        if self.exclude_enabled.get() and not excluded_types:
            self.show_error('除外するコンテンツを1つ以上選択するか、「指定コンテンツを除外」のチェックを外してください。')
            return
        if limit is None:limit=self.initial_path_limit
        priority=FALLBACK_CHOICES[self.fallback_priority.get()]
        fallback_priority=None if priority=='none' else priority
        region=self.region
        self.clear_result()
        self.selecting.set(False)
        self.canvas.configure(cursor='')
        self.show_input()
        self.page_limit = limit
        self.requested_page = selected_page
        self.busy = True
        self.entry.configure(state='disabled')
        self.browse_button.configure(state='disabled')
        self.paste_button.configure(state='disabled')
        self.analyze_button.configure(state='disabled')
        self.select_button.configure(state='disabled')
        self.reset_region_button.configure(state='disabled')
        self.fallback_combo.configure(state='disabled')
        self.repeat_check.configure(state='disabled')
        self.exclude_check.configure(state='disabled')
        self.content_list.configure(state='disabled')
        self.status.configure(text='解析中…',foreground='#26374a')
        self.set_details('盤面と接続を確認しています。')
        self.progress.pack(fill='x',pady=(0,10),before=self.body)
        self.progress.start(12)
        self.worker_thread=threading.Thread(target=self.worker,args=(source.resolve(),limit,region,avoid_repeated,excluded_types,fallback_priority),daemon=True)
        self.worker_thread.start()

    def worker(self,source,limit,region,avoid_repeated=False,excluded_types=(),fallback_priority='stage'):
        try:
            self.messages.put(('done',analyze_file(source,self.output_root,limit,region,
                                                           on_created=self.session_outputs.add_directory,
                                                           avoid_repeated=avoid_repeated,excluded_types=excluded_types,fallback_priority=fallback_priority)))
        except Exception as exc:
            self.messages.put(('failed',str(exc)))

    def poll(self):
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.closed or self.closing:
            return
        try:
            kind,payload = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            self.progress.pack_forget()
            for widget in (self.entry,self.browse_button,self.paste_button,self.analyze_button,self.select_button,self.reset_region_button):
                widget.configure(state='normal')
            self.fallback_combo.configure(state='readonly')
            self.repeat_check.configure(state='normal')
            self.exclude_check.configure(state='normal')
            self.content_list.configure(state='normal' if self.exclude_enabled.get() else 'disabled')
            if kind == 'failed':
                self.show_error('解析処理を完了できませんでした。\n\n'+payload)
            else:
                result,self.destination,self.image = payload
                self.result = result
                self.result_image = self.image
                self.showing_input = False
                title,details,success = describe_result(result)
                self.status.configure(text=title,foreground='#9a6700' if result['status']=='partial' else ('#147447' if success else '#b42318'))
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
        if self.result is None or self.result['status'] not in ('ok','partial'):
            return
        self.page = page
        paths = self.result['paths']
        path = [(r-1,c-1) for r,c in paths[page]]
        self.showing_input = False
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
        if self.busy or self.result is None or self.result['status'] not in ('ok','partial'):
            return
        page = self.page + delta
        if 0 <= page < len(self.result['paths']):
            self.show_page(page)
        elif page == len(self.result['paths']) and self.result.get('paths_truncated',False):
            # Fetch additional optimal paths only when needed; retain the exact total.
            self.start(limit=self.page_limit*2,selected_page=page)

    def show_input(self):
        if self.input_image is None:
            return
        self.showing_input=True
        self.image=self.input_image
        self.canvas.configure(cursor='crosshair' if self.selecting.get() and not self.busy else '')
        self.zoom=None
        self.render()

    def show_result(self):
        if self.result is None:
            return
        self.selecting.set(False)
        self.drag_start=None
        self.canvas.configure(cursor='')
        self.showing_input=False
        self.zoom=None
        if self.result['status'] in ('ok','partial'):
            self.show_page(self.page)
        else:
            self.image=self.result_image
            self.render()

    def begin_selection(self):
        if self.busy or self.closing:
            return
        self.show_input()
        self.canvas.configure(cursor='crosshair' if self.selecting.get() else '')

    def clear_region(self):
        if self.busy or self.closing:
            return
        self.region=None
        self.clear_result()
        self.region_text.set('自動検出（画像全体）')
        self.status.configure(text='解析の準備ができました',foreground='#26374a')
        self.show_input()

    def input_point(self,event):
        x=(self.canvas.canvasx(event.x)-self.image_offset[0])/self.display_scale
        y=(self.canvas.canvasy(event.y)-self.image_offset[1])/self.display_scale
        h,w=self.input_image.shape[:2]
        return max(0,min(w,x)),max(0,min(h,y))

    def update_canvas_cursor(self):
        if self.busy or self.closing or self.image is None:
            cursor = ''
        elif self.selecting.get() and self.showing_input:
            cursor = 'crosshair'
        elif self.panning:
            cursor = 'fleur'
        elif (self.image.shape[1]*self.display_scale > self.canvas.winfo_width() or
              self.image.shape[0]*self.display_scale > self.canvas.winfo_height()):
            cursor = 'hand2'
        else:
            cursor = ''
        self.canvas.configure(cursor=cursor)

    def pointer_start(self,event):
        self.panning = False
        self.drag_start = None
        if self.busy or self.closing or self.image is None:
            return
        if self.selecting.get() and self.showing_input:
            self.selection_start(event)
        elif (self.image.shape[1]*self.display_scale > self.canvas.winfo_width() or
              self.image.shape[0]*self.display_scale > self.canvas.winfo_height()):
            self.canvas.scan_mark(event.x,event.y)
            self.panning = True
        self.update_canvas_cursor()

    def pointer_drag(self,event):
        if self.busy or self.closing:
            return
        if self.panning:
            self.canvas.scan_dragto(event.x,event.y,gain=1)
        elif self.selecting.get() and self.showing_input:
            self.selection_drag(event)

    def pointer_end(self,event):
        if self.panning:
            self.pointer_drag(event)
            self.panning = False
            self.update_canvas_cursor()
        elif self.selecting.get() and self.showing_input:
            self.selection_end(event)

    def selection_start(self,event):
        if self.busy or self.closing or not self.selecting.get() or not self.showing_input or self.input_image is None:
            return
        self.drag_start=self.input_point(event)

    def selection_drag(self,event):
        if self.drag_start is not None and not self.busy and not self.closing:
            self.draw_region((*self.drag_start,*self.input_point(event)))

    def selection_end(self,event):
        if self.drag_start is None or self.busy or self.closing:
            return
        import math
        a,b=self.drag_start,self.input_point(event)
        self.drag_start=None
        box=(math.floor(min(a[0],b[0])),math.floor(min(a[1],b[1])),
             math.ceil(max(a[0],b[0])),math.ceil(max(a[1],b[1])))
        if box[2]-box[0]<20 or box[3]-box[1]<20:
            self.set_details('指定範囲が小さすぎます。全50個のアイコンと接続線を含むように囲んでください。')
            self.render()
            return
        self.region=box
        self.clear_result()
        self.show_input()
        self.status.configure(text='解析範囲を指定しました',foreground='#26374a')
        self.region_text.set(f'解析範囲: ({box[0]}, {box[1]}) ～ ({box[2]}, {box[3]})')
        self.set_details('指定範囲内から盤面を検出します。全50アイコンと接続線が入っていることを確認して「解析」を押してください。')
        self.render()

    def draw_region(self,box):
        self.canvas.delete('region')
        if box is None or not self.showing_input:
            return
        x1,y1,x2,y2=box
        sx,sy=self.image_offset
        scale=self.display_scale
        self.canvas.create_rectangle(sx+x1*scale,sy+y1*scale,sx+x2*scale,sy+y2*scale,
                                     outline='#e07800',width=3,tags='region')

    def schedule_render(self,event=None):
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
        self.resize_id = self.root.after(80,self.render)

    def render(self):
        self.panning = False
        if self.resize_id is not None:
            self.root.after_cancel(self.resize_id)
        self.resize_id = None
        if self.closed or self.closing:
            return
        self.canvas.delete('all')
        width,height=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        if self.image is None:
            self.scale_text.set('')
            self.update_canvas_cursor()
            self.canvas.configure(scrollregion=(0,0,width,height))
            self.canvas.create_text(width/2,height/2,text='入力画像と解析結果をここに表示します',fill='#65768b',width=max(100,width-40))
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
        self.image_offset=((max(width,dw)-dw)/2,(max(height,dh)-dh)/2)
        self.canvas.create_image(max(width,dw)/2,max(height,dh)/2,image=self.photo)
        self.draw_region(self.region)
        self.canvas.configure(scrollregion=(0,0,max(width,dw),max(height,dh)))
        self.scale_text.set(f'{scale:.0%}')
        self.update_canvas_cursor()

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

    def save_settings(self):
        try:
            write_gui_settings(self.settings_path,{
                'delete_outputs_on_exit':self.delete_outputs.get(),
                'avoid_repeated':self.avoid_repeated.get(),
                'exclude_enabled':self.exclude_enabled.get(),
                'excluded_types':[key for i,key in enumerate(CONTENT_NAMES) if i in self.content_list.curselection()],
                'fallback_priority':FALLBACK_CHOICES[self.fallback_priority.get()],
                'initial_path_limit':self.initial_path_limit})
        except OSError as exc:
            self.set_details('設定を保存できませんでした。今回の選択は有効ですが、次回起動時には引き継がれません。\n'+str(exc))

    def close(self):
        if self.closed or self.closing:
            return
        self.closing=True
        self.progress.stop()
        self.save_settings()
        for callback in (self.poll_id,self.resize_id):
            if callback is not None:
                self.root.after_cancel(callback)
        self.poll_id=self.resize_id=None
        for widget in (self.entry,self.browse_button,self.paste_button,self.analyze_button,
                       self.select_button,self.reset_region_button,self.cleanup_check,
                       self.repeat_check,self.exclude_check,self.content_list,self.fallback_combo):
            widget.configure(state='disabled')
        self.status.configure(text='解析の完了を待って終了します…' if self.worker_thread and self.worker_thread.is_alive() else '終了処理中…')
        self.finish_close()

    def finish_close(self):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.close_wait_id=self.root.after(100,self.finish_close)
            return
        self.close_wait_id=None
        if self.delete_outputs.get():
            failures=self.session_outputs.cleanup()
            if failures:
                messagebox.showwarning('一部の出力を削除できませんでした',
                    '使用中のファイルや安全に削除できないファイルは残しました。\n\n'+'\n'.join(failures[:5]),parent=self.root)
        self.closed=True
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
