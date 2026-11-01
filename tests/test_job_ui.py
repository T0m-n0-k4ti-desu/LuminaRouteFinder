import tempfile,unittest
from pathlib import Path
import tkinter as tk
from tkinterdnd2 import TkinterDnD
from lumina_route_finder.ui.controller import Application
class JobUiTests(unittest.TestCase):
    def test_progress_keeps_busy_and_cancel_discards_already_queued_completion(self):
        try:root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw()
        with tempfile.TemporaryDirectory() as temp:
            app=Application(root,Path(temp)/'outputs',settings_path=Path(temp)/'settings.json')
            try:
                app.busy=True;app.messages.put(('progress','test-stage'));app.poll()
                self.assertTrue(app.busy);self.assertIn('test-stage',app.status.cget('text'))
                app.messages.put(('done','must not be unpacked after cancellation'))
                app.cancel_analysis();app.poll()
                self.assertFalse(app.busy);self.assertIsNone(app.result)
                self.assertIn('キャンセル',app.status.cget('text'))
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
