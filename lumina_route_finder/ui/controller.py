"""Desktop controller: input, analysis jobs, paging, settings and shutdown."""
import argparse
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import COPY, TkinterDnD
from ..analysis import analyze_file
from ..analysis_session import AnalysisCache, AnalysisCancelled
from ..errors import ErrorCode, RecognitionError, failure_issues
from ..error_messages import error_message, format_issues
from ..image_io import read_image
from ..render import render_route
from ..domain.catalog import CONTENT_NAMES
from ..session import SessionOutputs
from ..settings import (load_cleanup_setting, default_settings_path, migrate_cleanup_setting,
                        read_cleanup_setting, load_settings, save_settings as write_gui_settings)
from .options import FALLBACK_CHOICES
from .presentation import describe_result
from .view import ApplicationView
from .preview import ImagePreview


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
            self.settings_notice=error_message(ErrorCode.SETTINGS_MIGRATION_ERROR, str(exc))
        self.delete_outputs=tk.BooleanVar(master=root,value=initial_setting if self.settings_notice else load_cleanup_setting(self.settings_path))
        self.saved_options=initial_options if self.settings_notice else load_settings(self.settings_path)
        self.initial_path_limit=self.saved_options['initial_path_limit']
        self.analysis_cache=AnalysisCache()
        self.cancel_event=threading.Event()
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
        self.destination = None
        self.poll_id = None
        self.view = ApplicationView(self, root)
        self.preview = ImagePreview(self.view.canvas, self.view.selecting, self.view.scale_text,
                                    can_interact=lambda: not self.busy and not self.closing,
                                    is_closed=lambda: self.closed or self.closing,
                                    on_region_selected=self.apply_region, on_notice=self.set_details)
        self.set_details('パスを入力するか、画像を選択・ドロップして「解析」を押してください。\n\n対応形式: JPG / PNG / BMP\n\n結果の番号はアイコンの通過順です。')
        if self.settings_notice:
            self.set_details(self.settings_notice)
        self.render()
        self.poll_id = root.after(80,self.poll)

    def set_details(self,text):
        self.view.details.configure(state='normal')
        self.view.details.delete('1.0','end')
        self.view.details.insert('1.0',text)
        self.view.details.yview_moveto(0)
        self.view.details.configure(state='disabled')

    def clear_result(self):
        self.preview.drag_start = None
        self.result = self.board = None
        self.page = 0
        self.view.page_text.set('')
        self.view.previous_button.configure(state='disabled')
        self.view.next_button.configure(state='disabled')
        self.image = self.preview.photo = None
        self.preview.showing_input = False
        self.view.canvas.configure(cursor='')
        self.preview.zoom = None
        self.destination = None
        self.view.open_button.configure(state='disabled')
        self.view.output_label.configure(text='')
        self.render()

    def path_changed(self,*_):
        if self.busy or self.closing:
            return
        self.analysis_cache.clear()
        self.preview.input_image=None
        self.region=None
        self.view.selecting.set(False)
        self.view.region_text.set('自動検出（画像全体）')
        self.clear_result()
        value=self.view.path.get().strip().strip('"').strip("'")
        try:
            if value and Path(value).expanduser().is_file():
                self.preview.input_image=read_image(Path(value).expanduser())
                self.show_input()
        except RecognitionError:
            pass
        self.view.status.configure(text='解析の準備ができました' if self.view.path.get().strip() else '画像を指定してください',foreground='#26374a')
        self.set_details('入力画像を確認してください。必要なら「範囲指定」をオンにして盤面をドラッグで囲み、「解析」を押してください。')

    def browse(self):
        selected = filedialog.askopenfilename(parent=self.root,title='解析する画像を選択',
            filetypes=[('画像ファイル','*.jpg *.jpeg *.png *.bmp'),('すべてのファイル','*.*')])
        if selected:
            self.view.path.set(selected)

    def paste_image(self,event=None):
        if self.busy or self.closing:
            return 'break'
        try:
            from ..clipboard import get_clipboard_image
            image=get_clipboard_image()
            if image is None:
                if event is None:
                    self.show_error(error_message(ErrorCode.CLIPBOARD_EMPTY))
                return None
            self.load_pasted_image(image)
            return 'break'
        except NotImplementedError as exc:
            self.show_error(error_message(ErrorCode.CLIPBOARD_UNAVAILABLE, str(exc)))
            return 'break'
        except (ImportError,OSError,ValueError) as exc:
            self.show_error(error_message(ErrorCode.CLIPBOARD_READ_ERROR, str(exc)))
            return 'break'

    def load_pasted_image(self,image):
        from ..clipboard import save_clipboard_image
        path=save_clipboard_image(image,self.output_root)
        self.session_outputs.add_file(path)
        self.view.path.set(str(path))
        self.preview.input_image=read_image(path)
        self.show_input()
        self.view.status.configure(text='クリップボード画像を読み込みました',foreground='#26374a')
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
            self.show_error(error_message(ErrorCode.INVALID_FILE_COUNT))
            return 'refuse_drop'
        self.view.path.set(paths[0])
        return COPY

    def show_error(self,message):
        self.clear_result()
        self.view.status.configure(text='解析できませんでした',foreground='#b42318')
        self.set_details(message)

    def options_changed(self,event=None):
        if self.busy or self.closing:
            return
        self.view.content_list.configure(state='normal' if self.view.exclude_enabled.get() else 'disabled')
        if self.result is not None:
            self.clear_result()
            self.show_input()
            self.view.status.configure(text='探索条件を変更しました。「解析」を押してください。',foreground='#26374a')
            self.set_details('現在の条件で探索するには「解析」を押してください。')
        self.save_settings()

    def start(self, limit=None, selected_page=0):
        if self.busy or self.closing:
            return
        value = self.view.path.get().strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):
            value = value[1:-1]
        source = Path(value).expanduser()
        if not value or not source.is_file():
            self.show_error(error_message(ErrorCode.INPUT_NOT_FOUND))
            return
        avoid_repeated = self.view.avoid_repeated.get()
        excluded_types = tuple(list(CONTENT_NAMES)[i] for i in self.view.content_list.curselection()) if self.view.exclude_enabled.get() else ()
        if self.view.exclude_enabled.get() and not excluded_types:
            self.show_error(error_message(ErrorCode.MISSING_EXCLUSION_TARGET))
            return
        if limit is None:limit=self.initial_path_limit
        priority=FALLBACK_CHOICES[self.view.fallback_priority.get()]
        fallback_priority=None if priority=='none' else priority
        region=self.region
        self.clear_result()
        self.view.selecting.set(False)
        self.view.canvas.configure(cursor='')
        self.show_input()
        self.page_limit = limit
        self.requested_page = selected_page
        self.cancel_event.clear()
        self.view.cancel_button.configure(state='normal')
        self.busy = True
        self.view.entry.configure(state='disabled')
        self.view.browse_button.configure(state='disabled')
        self.view.paste_button.configure(state='disabled')
        self.view.analyze_button.configure(state='disabled')
        self.view.select_button.configure(state='disabled')
        self.view.reset_region_button.configure(state='disabled')
        self.view.fallback_combo.configure(state='disabled')
        self.view.repeat_check.configure(state='disabled')
        self.view.exclude_check.configure(state='disabled')
        self.view.content_list.configure(state='disabled')
        self.view.status.configure(text='解析中…',foreground='#26374a')
        self.set_details('盤面と接続を確認しています。')
        self.view.progress.pack(fill='x',pady=(0,10),before=self.view.body)
        self.view.progress.start(12)
        self.worker_thread=threading.Thread(target=self.worker,args=(source.resolve(),limit,region,avoid_repeated,excluded_types,fallback_priority),daemon=True)
        self.worker_thread.start()

    def worker(self,source,limit,region,avoid_repeated=False,excluded_types=(),fallback_priority='stage'):
        try:
            self.messages.put(('done',analyze_file(source,self.output_root,limit,region,
                                                           on_created=self.session_outputs.add_directory,
                                                           avoid_repeated=avoid_repeated,excluded_types=excluded_types,fallback_priority=fallback_priority,cache=self.analysis_cache,cancel=self.cancel_event,
                                                           progress=lambda stage:self.messages.put(('progress',stage)))))
        except AnalysisCancelled:
            self.messages.put(('cancelled',None))
        except Exception as exc:
            self.messages.put(('failed',failure_issues(exc)))

    def cancel_analysis(self):
        if self.busy:
            self.cancel_event.set()
            self.view.cancel_button.configure(state='disabled')
            self.view.status.configure(text='停止待ち…（現在の処理区切りで停止します）')

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
            if kind=='progress':
                if not self.cancel_event.is_set():self.view.status.configure(text=payload+'…')
                self.poll_id=self.root.after(20,self.poll)
                return
            self.view.cancel_button.configure(state='disabled')
            self.busy = False
            self.view.progress.stop()
            self.view.progress.pack_forget()
            for widget in (self.view.entry,self.view.browse_button,self.view.paste_button,self.view.analyze_button,self.view.select_button,self.view.reset_region_button):
                widget.configure(state='normal')
            self.view.fallback_combo.configure(state='readonly')
            self.view.repeat_check.configure(state='normal')
            self.view.exclude_check.configure(state='normal')
            self.view.content_list.configure(state='normal' if self.view.exclude_enabled.get() else 'disabled')
            if kind=='cancelled':
                self.view.status.configure(text='解析をキャンセルしました',foreground='#26374a')
                self.set_details('設定や範囲を変更して再度解析できます。')
            elif kind == 'failed':
                self.show_error(format_issues(payload, include_detail=True))
            else:
                result,self.destination,self.image = payload
                self.result = result
                self.result_image = self.image
                self.preview.showing_input = False
                title,details,success = describe_result(result)
                self.view.status.configure(text=title,foreground='#9a6700' if result['status']=='partial' else ('#147447' if success else '#b42318'))
                self.set_details(details)
                self.view.output_label.configure(text=f'保存先:\n{self.destination.resolve()}')
                self.view.open_button.configure(state='normal')
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
        self.preview.showing_input = False
        self.image = render_route(self.board,path)
        _,details,_ = describe_result(self.result,page)
        self.set_details(details)
        total = self.result['optimal_path_count']
        self.view.page_text.set(f'候補 {page+1} / {total}')
        self.view.previous_button.configure(state='normal' if page else 'disabled')
        more = page+1 < len(paths) or self.result.get('paths_truncated',False)
        self.view.next_button.configure(state='normal' if more else 'disabled')
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
        if self.preview.input_image is None:
            return
        self.preview.showing_input=True
        self.image=self.preview.input_image
        self.view.canvas.configure(cursor='crosshair' if self.view.selecting.get() and not self.busy else '')
        self.preview.zoom=None
        self.render()

    def show_result(self):
        if self.result is None:
            return
        self.view.selecting.set(False)
        self.preview.drag_start=None
        self.view.canvas.configure(cursor='')
        self.preview.showing_input=False
        self.preview.zoom=None
        if self.result['status'] in ('ok','partial'):
            self.show_page(self.page)
        else:
            self.image=self.result_image
            self.render()

    def begin_selection(self):
        if self.busy or self.closing:
            return
        self.show_input()
        self.view.canvas.configure(cursor='crosshair' if self.view.selecting.get() else '')

    def clear_region(self):
        if self.busy or self.closing:
            return
        self.region=None
        self.analysis_cache.clear()
        self.clear_result()
        self.view.region_text.set('自動検出（画像全体）')
        self.view.status.configure(text='解析の準備ができました',foreground='#26374a')
        self.show_input()

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
            self.set_details(error_message(ErrorCode.OUTPUT_OPEN_ERROR, f'{self.destination}\n\n{exc}'))

    def save_settings(self):
        try:
            write_gui_settings(self.settings_path,{
                'delete_outputs_on_exit':self.delete_outputs.get(),
                'avoid_repeated':self.view.avoid_repeated.get(),
                'exclude_enabled':self.view.exclude_enabled.get(),
                'excluded_types':[key for i,key in enumerate(CONTENT_NAMES) if i in self.view.content_list.curselection()],
                'fallback_priority':FALLBACK_CHOICES[self.view.fallback_priority.get()],
                'initial_path_limit':self.initial_path_limit})
        except OSError as exc:
            self.set_details(error_message(ErrorCode.SETTINGS_SAVE_ERROR, str(exc)))

    def close(self):
        if self.closed or self.closing:
            return
        self.closing=True
        self.cancel_event.set()
        self.view.progress.stop()
        self.save_settings()
        for callback in (self.poll_id,self.preview.resize_id):
            if callback is not None:
                self.root.after_cancel(callback)
        self.poll_id=self.preview.resize_id=None
        for widget in (self.view.entry,self.view.browse_button,self.view.paste_button,self.view.analyze_button,
                       self.view.select_button,self.view.reset_region_button,self.view.cleanup_check,
                       self.view.repeat_check,self.view.exclude_check,self.view.content_list,self.view.fallback_combo):
            widget.configure(state='disabled')
        self.view.status.configure(text='解析の完了を待って終了します…' if self.worker_thread and self.worker_thread.is_alive() else '終了処理中…')
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
                    error_message(ErrorCode.OUTPUT_CLEANUP_ERROR, '\n'.join(failures[:5])),parent=self.root)
        self.closed=True
        self.root.destroy()

    @property
    def image(self):
        return self.preview.image

    @image.setter
    def image(self, value):
        self.preview.image = value

    @property
    def region(self):
        return self.preview.region

    @region.setter
    def region(self, value):
        self.preview.region = value

    @property
    def path(self):
        return self.view.path

    @property
    def status(self):
        return self.view.status

    def render(self):
        self.preview.render()

    def apply_region(self, box):
        self.analysis_cache.clear()
        self.region = box
        self.clear_result()
        self.show_input()
        self.view.status.configure(text='解析範囲を指定しました',foreground='#26374a')
        self.view.region_text.set(f'解析範囲: ({box[0]}, {box[1]}) ～ ({box[2]}, {box[3]})')
        self.set_details('指定範囲内から盤面を検出します。全50アイコンと接続線が入っていることを確認して「解析」を押してください。')
        self.render()


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
