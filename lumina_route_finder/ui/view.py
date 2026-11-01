"""Widget layout and event wiring; no recognition, file IO or worker lifecycle."""
import tkinter as tk
from tkinter import ttk
from tkinterdnd2 import DND_FILES
from ..domain.catalog import CONTENT_NAMES
from .options import FALLBACK_CHOICES


class ApplicationView:
    def __init__(self, controller, root):
        root.title('LuminaRouteFinder — 最大経路検索')
        root.geometry('1100x840')
        root.minsize(850, 620)
        root.protocol('WM_DELETE_WINDOW', controller.close)
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
        self.browse_button = ttk.Button(inputs,text='画像を選択…',command=controller.browse)
        self.browse_button.pack(side='left',padx=8)
        self.paste_button = ttk.Button(inputs,text='貼り付け',command=controller.paste_image)
        self.paste_button.pack(side='left',padx=(0,8))
        self.analyze_button = ttk.Button(inputs,text='解析',command=controller.start)
        self.analyze_button.pack(side='left')
        self.cancel_button=ttk.Button(inputs,text='中止',command=controller.cancel_analysis,state='disabled')
        self.cancel_button.pack(side='left',padx=(6,0))
        ttk.Button(inputs,text='設定・プリセット',command=controller.open_preferences).pack(side='left',padx=(6,0))
        self.drop_label = tk.Label(main,text='画像をドロップ、またはCtrl＋Vで貼り付けできます（1枚）',
                                   bg='#eef3f8',fg='#42556b',pady=12,highlightthickness=1,highlightbackground='#b8c9da')
        self.drop_label.pack(fill='x',pady=(10,12))
        summary=ttk.Frame(main)
        summary.pack(fill='x',pady=(0,10))
        self.summary_text=tk.StringVar(master=root)
        self.summary_label=ttk.Label(summary,textvariable=self.summary_text,wraplength=700)
        self.summary_label.pack(side='left',fill='x',expand=True)
        self.quick_settings_button=ttk.Button(summary,text='クイック設定を表示',command=lambda:self.toggle_quick_settings(controller))
        self.quick_settings_button.pack(side='right',padx=(10,0))
        summary.bind('<Configure>',lambda event:self.summary_label.configure(wraplength=max(180,event.width-self.quick_settings_button.winfo_reqwidth()-12)))
        self.quick_settings_visible=False
        self.options_frame=options=ttk.LabelFrame(main,text='クイック設定（設定画面からも変更できます）',padding=8)
        self.avoid_repeated = tk.BooleanVar(master=root,value=controller.saved_options['avoid_repeated'])
        self.exclude_enabled = tk.BooleanVar(master=root,value=controller.saved_options['exclude_enabled'])
        self.repeat_check = ttk.Checkbutton(options,text='同じコンテンツの連続を禁止',variable=self.avoid_repeated,
                                            command=controller.options_changed)
        self.repeat_check.grid(row=0,column=0,sticky='w',padx=(0,20))
        self.exclude_check = ttk.Checkbutton(options,text='指定コンテンツを除外',variable=self.exclude_enabled,
                                             command=controller.options_changed)
        self.exclude_check.grid(row=0,column=1,sticky='w')
        self.content_list = tk.Listbox(options,selectmode='multiple',exportselection=False,height=4,width=32)
        for name in CONTENT_NAMES.values():
            self.content_list.insert('end',name)
        for i,key in enumerate(CONTENT_NAMES):
            if key in controller.saved_options['excluded_types']:self.content_list.selection_set(i)
        self.content_list.grid(row=1,column=1,sticky='ew',pady=(5,0))
        scroll = ttk.Scrollbar(options,orient='vertical',command=self.content_list.yview)
        scroll.grid(row=1,column=2,sticky='ns',pady=(5,0))
        self.content_list.configure(yscrollcommand=scroll.set,state='normal' if self.exclude_enabled.get() else 'disabled')
        ttk.Label(options,text='除外する種類をクリックして選択・解除できます（複数可）。',wraplength=330).grid(row=1,column=0,sticky='w',padx=(0,20))
        self.content_list.bind('<<ListboxSelect>>',controller.options_changed)
        ttk.Label(options,text='ゴール未到達時').grid(row=2,column=0,sticky='w',pady=(8,0))
        initial_choice=next(label for label,key in FALLBACK_CHOICES.items() if key==controller.saved_options['fallback_priority'])
        self.fallback_priority=tk.StringVar(master=root,value=initial_choice)
        self.fallback_combo=ttk.Combobox(options,textvariable=self.fallback_priority,values=list(FALLBACK_CHOICES),state='readonly',width=30)
        self.fallback_combo.grid(row=2,column=1,sticky='ew',pady=(8,0))
        self.fallback_combo.bind('<<ComboboxSelected>>',controller.options_changed)
        self.objective_label=ttk.Label(options,text='経路評価: '+{'count':'通過数最大','weight':'重み合計最大','count_then_weight':'通過数優先・同数時に重み'}[controller.objective])
        self.objective_label.grid(row=3,column=0,columnspan=2,sticky='w',pady=(6,0))
        self.cleanup_check=ttk.Checkbutton(options,text='終了時に今回の出力（解析結果・貼り付け画像）を削除',variable=controller.delete_outputs,command=controller.save_settings)
        self.cleanup_check.grid(row=4,column=0,columnspan=3,sticky='w',pady=(8,0))
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
        self.controls=ttk.Frame(preview_frame)
        self.controls.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(8,0))
        self.controls.columnconfigure(0,weight=1)
        self.controls.columnconfigure(1,weight=1)
        self.zoom_tools=ttk.Frame(self.controls)
        ttk.Button(self.zoom_tools,text='全体表示',command=lambda:controller.preview.fit()).pack(side='left')
        ttk.Button(self.zoom_tools,text='＋',width=4,command=lambda:controller.preview.change_zoom(1.25)).pack(side='left',padx=4)
        ttk.Button(self.zoom_tools,text='－',width=4,command=lambda:controller.preview.change_zoom(.8)).pack(side='left')
        self.scale_text=tk.StringVar(value='')
        ttk.Label(self.zoom_tools,textvariable=self.scale_text,width=5).pack(side='left',padx=(6,0))
        self.pages=ttk.Frame(self.controls)
        self.previous_button=ttk.Button(self.pages,text='← 前へ',command=lambda:controller.change_page(-1),state='disabled')
        self.previous_button.pack(side='left')
        self.page_text=tk.StringVar(value='')
        self.page_label=ttk.Label(self.pages,textvariable=self.page_text)
        self.page_label.pack(side='left',padx=8)
        self.next_button=ttk.Button(self.pages,text='次へ →',command=lambda:controller.change_page(1),state='disabled')
        self.next_button.pack(side='left')
        self.source_tools=ttk.Frame(self.controls)
        ttk.Button(self.source_tools,text='入力画像',command=controller.show_input).pack(side='left')
        ttk.Button(self.source_tools,text='解析結果',command=controller.show_result).pack(side='left',padx=5)
        self.selecting=tk.BooleanVar(value=False)
        self.select_button=ttk.Checkbutton(self.source_tools,text='範囲指定',variable=self.selecting,command=controller.begin_selection)
        self.select_button.pack(side='left')
        self.reset_region_button=ttk.Button(self.source_tools,text='範囲解除',command=controller.clear_region)
        self.reset_region_button.pack(side='left',padx=5)
        self.inspection_tools=ttk.Frame(self.controls)
        ttk.Button(self.inspection_tools,text='認識確認・補正',command=controller.open_recognition).pack(side='left')
        ttk.Button(self.inspection_tools,text='未到達の原因・比較',command=controller.open_diagnostics).pack(side='left',padx=(5,0))
        self.region_text=tk.StringVar(value='自動検出（画像全体）')
        self.region_label=ttk.Label(self.controls,textvariable=self.region_text,wraplength=650)
        self.controls.bind('<Configure>',lambda event:self.layout_controls(event.width))
        self.controls_layout=None
        self.layout_controls(700)
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
        self.details.tag_configure('step-focus',background='#ffe29a')
        self.details.bind('<ButtonRelease-1>',controller.details_clicked)
        self.open_button = ttk.Button(sidebar,text='結果フォルダーを開く',command=controller.open_output,state='disabled')
        self.open_button.grid(row=2,column=0,sticky='ew',pady=(12,0))
        actions=ttk.Frame(sidebar)
        actions.grid(row=4,column=0,sticky='ew',pady=(8,0))
        ttk.Button(actions,text='候補保存',command=controller.save_candidate).pack(side='left')
        ttk.Button(actions,text='画像コピー',command=controller.copy_candidate).pack(side='left',padx=3)
        ttk.Button(actions,text='順序コピー',command=controller.copy_steps).pack(side='left')
        self.output_label = ttk.Label(sidebar,text='',wraplength=300)
        self.output_label.grid(row=3,column=0,sticky='ew',pady=(8,0))
        for widget in (self.entry,self.drop_label,self.canvas):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>',controller.on_drop)
        self.path.trace_add('write',controller.path_changed)
        self.entry.bind('<Return>',lambda event:controller.start())
        root.bind('<Control-v>',controller.paste_image)
        root.bind('<Control-V>',controller.paste_image)


    def refresh_summary(self,controller):
        names={'count':'通過数最大','weight':'重み合計最大','count_then_weight':'通過数優先・同数時に重み'}
        excluded=len(self.content_list.curselection())
        exclusion_text=(f'{excluded}種類' if excluded else '未選択') if self.exclude_enabled.get() else '無効'
        fallback=FALLBACK_CHOICES[self.fallback_priority.get()]
        fallback_text={'stage':'段階優先','count':'通過数優先' if controller.objective=='count' else '経路評価優先','none':'途中経路なし'}[fallback]
        parts=[names[controller.objective],
               '連続禁止: '+('有効' if self.avoid_repeated.get() else '無効'),
               '除外: '+exclusion_text,
               '未到達: '+fallback_text,
               '終了時削除: '+('有効' if controller.delete_outputs.get() else '無効')]
        self.summary_text.set(' / '.join(parts))

    def toggle_quick_settings(self,controller):
        if controller.busy or controller.closing:return
        self.quick_settings_visible=not self.quick_settings_visible
        if self.quick_settings_visible:
            self.options_frame.pack(fill='x',pady=(0,10),before=self.body)
        else:self.options_frame.pack_forget()
        self.quick_settings_button.configure(text='クイック設定を隠す' if self.quick_settings_visible else 'クイック設定を表示')

    def layout_controls(self,width):
        narrow=width<620
        self.region_label.configure(wraplength=max(180,width-8))
        peer=self.zoom_tools if narrow else self.inspection_tools
        self.page_label.configure(wraplength=max(60,width-peer.winfo_reqwidth()-self.previous_button.winfo_reqwidth()-self.next_button.winfo_reqwidth()-24))
        if self.controls_layout==narrow:return
        self.controls_layout=narrow
        for widget in (self.zoom_tools,self.pages,self.source_tools,self.inspection_tools,self.region_label):widget.grid_forget()
        self.source_tools.grid(row=0,column=0,columnspan=2 if narrow else 1,sticky='w')
        self.zoom_tools.grid(row=1 if narrow else 0,column=0 if narrow else 1,sticky='w' if narrow else 'e',pady=(5,0) if narrow else 0)
        self.inspection_tools.grid(row=2 if narrow else 1,column=0,columnspan=2 if narrow else 1,sticky='w',pady=(5,0))
        self.pages.grid(row=1,column=1,sticky='e',pady=(5,0))
        self.region_label.grid(row=3 if narrow else 2,column=0,columnspan=2,sticky='ew',pady=(4,0))
