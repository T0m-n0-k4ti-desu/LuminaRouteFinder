"""Validated preferences and named search presets."""
import math
import tkinter as tk
from tkinter import ttk, messagebox
from ..domain.catalog import CONTENT_NAMES
from ..storage.settings import DEFAULT_SETTINGS, normalize_search
from .options import FALLBACK_CHOICES

OBJECTIVES={'通過数最大':'count','重み合計最大':'weight','通過数優先・同数時に重み':'count_then_weight'}

class PreferencesDialog:
    def __init__(self,app):
        self.app=app
        self.window=tk.Toplevel(app.root);self.window.title('設定・探索条件プリセット');self.window.geometry('640x720')
        self.window.transient(app.root)
        tabs=ttk.Notebook(self.window);tabs.pack(fill='both',expand=True,padx=12,pady=12)
        general=ttk.Frame(tabs,padding=12);weights=ttk.Frame(tabs,padding=12);presets=ttk.Frame(tabs,padding=12)
        tabs.add(general,text='設定');tabs.add(weights,text='種類別の重み');tabs.add(presets,text='プリセット')
        self.repeat=tk.BooleanVar();self.exclude=tk.BooleanVar();self.cleanup=tk.BooleanVar(value=app.delete_outputs.get())
        self.objective=tk.StringVar();self.fallback=tk.StringVar();self.limit=tk.StringVar(value=str(app.initial_path_limit))
        ttk.Label(general,text='最初に取得する候補数（1～1000）').pack(anchor='w')
        ttk.Spinbox(general,from_=1,to=1000,textvariable=self.limit,width=10).pack(anchor='w',pady=5)
        ttk.Checkbutton(general,text='終了時に今回の生成物を削除',variable=self.cleanup).pack(anchor='w',pady=5)
        ttk.Checkbutton(general,text='同じコンテンツの連続を禁止',variable=self.repeat).pack(anchor='w',pady=5)
        ttk.Checkbutton(general,text='選んだ種類を除外',variable=self.exclude).pack(anchor='w',pady=5)
        kind_frame=ttk.Frame(general);kind_frame.pack(fill='x')
        self.kinds=tk.Listbox(kind_frame,selectmode='multiple',exportselection=False,height=6)
        for name in CONTENT_NAMES.values():self.kinds.insert('end',name)
        kind_scroll=ttk.Scrollbar(kind_frame,orient='vertical',command=self.kinds.yview)
        self.kinds.configure(yscrollcommand=kind_scroll.set)
        self.kinds.pack(side='left',fill='x',expand=True);kind_scroll.pack(side='right',fill='y')
        for label,var,values in [('経路の評価方法',self.objective,OBJECTIVES),('ゴール未到達時',self.fallback,FALLBACK_CHOICES)]:
            ttk.Label(general,text=label).pack(anchor='w',pady=(10,0))
            ttk.Combobox(general,textvariable=var,values=list(values),state='readonly',width=38).pack(anchor='w',pady=5)
        ttk.Label(general,text='重み付け時の未到達経路は、到達段階を優先、または選択した経路評価を優先します。',wraplength=550).pack(anchor='w',pady=8)
        ttk.Button(general,text='初期設定を読み込む（適用で確定）',command=self.defaults).pack(anchor='w',pady=8)
        self.weight_vars={}
        for row,(key,name) in enumerate(CONTENT_NAMES.items()):
            ttk.Label(weights,text=name).grid(row=row,column=0,sticky='w',pady=4)
            var=tk.StringVar();self.weight_vars[key]=var
            ttk.Entry(weights,textvariable=var,width=12).grid(row=row,column=1,padx=12)
        ttk.Label(weights,text='各種類の初期値は1。負の重みも指定できます（±1,000,000以内）。',wraplength=500).grid(row=len(CONTENT_NAMES),column=0,columnspan=2,pady=12)
        self.name=tk.StringVar()
        ttk.Label(presets,text='プリセット名').pack(anchor='w')
        self.names=ttk.Combobox(presets,textvariable=self.name,values=list(app.presets));self.names.pack(fill='x',pady=8)
        ttk.Button(presets,text='読み込む（適用で確定）',command=self.load_preset).pack(anchor='w',pady=5)
        ttk.Button(presets,text='現在の条件を保存',command=self.save_preset).pack(anchor='w',pady=5)
        ttk.Button(presets,text='削除',command=self.delete_preset).pack(anchor='w',pady=5)
        ttk.Label(presets,text='種類の選択・連続禁止・未到達時優先順位・評価方法・重みを保存します。候補数と終了時削除は共通設定です。',wraplength=550).pack(anchor='w',pady=15)
        footer=ttk.Frame(self.window,padding=12);footer.pack(fill='x')
        ttk.Button(footer,text='適用',command=self.apply).pack(side='right')
        ttk.Button(footer,text='閉じる',command=self.window.destroy).pack(side='right',padx=8)
        self.populate(app.current_search())
    def populate(self,values):
        values=normalize_search(values)
        self.repeat.set(values['avoid_repeated']);self.exclude.set(values['exclude_enabled'])
        self.kinds.selection_clear(0,'end')
        for i,key in enumerate(CONTENT_NAMES):
            if key in values['excluded_types']:self.kinds.selection_set(i)
        self.objective.set(next(k for k,v in OBJECTIVES.items() if v==values['objective']))
        self.fallback.set(next(k for k,v in FALLBACK_CHOICES.items() if v==values['fallback_priority']))
        for key,var in self.weight_vars.items():var.set(str(values['weights'].get(key,1)))
    def values(self):
        weights={k:float(v.get()) for k,v in self.weight_vars.items()}
        if any(not math.isfinite(v) or abs(v)>1000000 for v in weights.values()):raise ValueError('重みは±1,000,000以内の有限数で指定してください。')
        return {'avoid_repeated':self.repeat.get(),'exclude_enabled':self.exclude.get(),'excluded_types':[k for i,k in enumerate(CONTENT_NAMES) if i in self.kinds.curselection()],
            'objective':OBJECTIVES[self.objective.get()],'fallback_priority':FALLBACK_CHOICES[self.fallback.get()],'weights':weights}
    def defaults(self):
        self.populate(DEFAULT_SETTINGS);self.limit.set('20');self.cleanup.set(True)
    def apply(self):
        if self.app.busy or self.app.closing:return
        try:
            values=self.values();limit=int(self.limit.get())
            if not 1<=limit<=1000:raise ValueError('候補数は1～1000で指定してください。')
        except (ValueError,KeyError) as exc:
            messagebox.showerror('設定を確認してください',str(exc),parent=self.window);return
        self.app.initial_path_limit=limit;self.app.delete_outputs.set(self.cleanup.get());self.app.apply_search(values)
    def load_preset(self):
        if self.name.get() in self.app.presets:self.populate(self.app.presets[self.name.get()])
    def save_preset(self):
        if self.app.busy or self.app.closing:return
        name=self.name.get().strip()
        if not name or len(name)>80:
            messagebox.showerror('プリセット名','1～80文字で指定してください。',parent=self.window);return
        try:values=self.values()
        except (ValueError,KeyError) as exc:
            messagebox.showerror('設定を確認してください',str(exc),parent=self.window);return
        if name in self.app.presets and not messagebox.askyesno('上書き確認',name+' を上書きしますか？',parent=self.window):return
        self.app.presets[name]=values;self.app.save_settings();self.names.configure(values=list(self.app.presets))
    def delete_preset(self):
        name=self.name.get()
        if self.app.busy or self.app.closing or name not in self.app.presets:return
        if messagebox.askyesno('削除確認',name+' を削除しますか？',parent=self.window):
            del self.app.presets[name];self.app.save_settings();self.names.configure(values=list(self.app.presets));self.name.set('')
