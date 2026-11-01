import tempfile,unittest
from pathlib import Path
import tkinter as tk
from tkinterdnd2 import TkinterDnD
from lumina_route_finder.ui.controller import Application
from lumina_route_finder.ui.preferences import PreferencesDialog
class CompactLayoutTests(unittest.TestCase):
    def setUp(self):
        try:self.root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.root.withdraw();self.temp=tempfile.TemporaryDirectory()
        self.app=Application(self.root,Path(self.temp.name)/'outputs',settings_path=Path(self.temp.name)/'settings.json');self.root.update()
    def tearDown(self):
        if hasattr(self,'app'):self.root.update_idletasks();self.app.close();self.temp.cleanup()
    def test_quick_settings_are_hidden_initially_and_toggle_without_changing_values(self):
        self.assertEqual(self.app.view.options_frame.winfo_manager(),'')
        self.assertIs(self.app.view.cleanup_check.master,self.app.view.options_frame)
        before=self.app.current_search()
        self.app.view.toggle_quick_settings(self.app)
        self.assertEqual(self.app.view.options_frame.winfo_manager(),'pack')
        self.app.view.toggle_quick_settings(self.app)
        self.assertEqual(self.app.view.options_frame.winfo_manager(),'')
        self.assertEqual(self.app.current_search(),before)
    def test_preferences_apply_updates_hidden_state_and_visible_summary(self):
        dialog=PreferencesDialog(self.app)
        dialog.repeat.set(True);dialog.exclude.set(True);dialog.kinds.selection_set(0)
        dialog.cleanup.set(False);dialog.fallback.set('通過アイコン数を優先');dialog.objective.set('重み合計最大');dialog.apply()
        summary=self.app.view.summary_text.get()
        for expected in ['重み合計最大','連続禁止: 有効','除外: 1種類','未到達: 経路評価優先','終了時削除: 無効']:self.assertIn(expected,summary)
        self.assertEqual(self.app.view.options_frame.winfo_manager(),'')
        self.assertFalse(self.app.delete_outputs.get())
    def test_controls_fit_default_and_minimum_width_with_large_candidate_count(self):
        self.root.deiconify()
        self.app.view.page_text.set('候補 12345 / 1234567890123456')
        for geometry,narrow in [('1100x840',False),('850x620',True)]:
            self.root.geometry(geometry);self.root.update();self.root.update_idletasks();self.root.update()
            view=self.app.view
            self.assertEqual(view.controls_layout,narrow)
            for group in (view.source_tools,view.zoom_tools,view.pages,view.inspection_tools):
                self.assertGreaterEqual(group.winfo_x(),0)
                self.assertLessEqual(group.winfo_x()+group.winfo_width(),view.controls.winfo_width()+1)
            self.assertGreater(view.canvas.winfo_height(),240)
if __name__=='__main__':unittest.main()
