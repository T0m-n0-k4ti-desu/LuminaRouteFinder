import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from tkinterdnd2 import TkinterDnD
import numpy as np
from lumina_route_finder.ui.controller import Application
from lumina_route_finder.image_io import read_image
class InteractionTests(unittest.TestCase):
    def test_page_focus_export_and_clipboard_dispatch(self):
        try:root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw()
        with tempfile.TemporaryDirectory() as temp:
            app=Application(root,Path(temp)/'outputs',settings_path=Path(temp)/'settings.json')
            try:
                app.result={'status':'ok','max_count':2,'optimal_path_count':2,'paths':[[[1,1],[2,1]],[[1,2],[2,2]]]}
                app.board=np.zeros((500,260,3),dtype=np.uint8)
                app.show_page(1);plain=app.image.copy();app.focus_step(1)
                self.assertFalse(np.array_equal(plain,app.image));self.assertTrue(app.view.details.tag_ranges('step-focus'))
                target=Path(temp)/'export.png'
                with patch('lumina_route_finder.ui.controller.filedialog.asksaveasfilename',return_value=str(target)):app.save_candidate()
                self.assertTrue(np.array_equal(read_image(target),app.candidate_image()))
                with patch('lumina_route_finder.route_export.copy_image') as copy:
                    app.copy_candidate();self.assertTrue(np.array_equal(copy.call_args.args[0],app.candidate_image()))
                app.show_page(0);self.assertIsNone(app.selected_step)
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
