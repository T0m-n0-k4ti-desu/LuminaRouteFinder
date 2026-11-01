import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from tkinterdnd2 import TkinterDnD
from lumina_route_finder.ui.controller import Application
from lumina_route_finder.ui.preferences import PreferencesDialog
from lumina_route_finder.settings import load_settings
class PreferencesTests(unittest.TestCase):
    def test_apply_validation_preset_restore_delete_and_restart_data(self):
        try:root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw()
        with tempfile.TemporaryDirectory() as temp:
            app=Application(root,Path(temp)/'outputs',settings_path=Path(temp)/'settings.json')
            dialog=PreferencesDialog(app)
            try:
                dialog.objective.set('重み合計最大');dialog.weight_vars['escape_room'].set('-2.5');dialog.repeat.set(True);dialog.limit.set('3')
                dialog.name.set('test');dialog.save_preset()
                dialog.defaults();dialog.name.set('test');dialog.load_preset();dialog.apply()
                self.assertEqual(app.objective,'weight');self.assertEqual(app.weights['escape_room'],-2.5)
                self.assertTrue(app.view.avoid_repeated.get())
                saved=load_settings(app.settings_path)
                self.assertIn('test',saved['presets']);self.assertEqual(saved['objective'],'weight')
                previous=app.initial_path_limit;dialog.limit.set('0')
                with patch('lumina_route_finder.ui.preferences.messagebox.showerror') as error:
                    dialog.apply();error.assert_called_once()
                self.assertEqual(app.initial_path_limit,previous)
                with patch('lumina_route_finder.ui.preferences.messagebox.askyesno',return_value=True):dialog.delete_preset()
                self.assertNotIn('test',load_settings(app.settings_path)['presets'])
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
