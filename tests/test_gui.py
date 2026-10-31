from pathlib import Path
import os
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from tkinterdnd2 import TkinterDnD
from lumina_route_finder.gui import Application, analyze_file, describe_result

ROOT=Path(os.environ.get('LUMINA_SAMPLE_ROOT',str(Path(__file__).resolve().parents[2])))
NORMAL=ROOT/'sample_image/TWCI_2026_11_1_1_2_47.jpg'
ERROR=ROOT/'error_images/TWCI_2026_11_1_1_29_33.jpg'


class ResultDescriptionTests(unittest.TestCase):
    def test_error_reasons_are_translated(self):
        title,details,success=describe_result({'status':'error','errors':[{'code':'CURSOR_OCCLUSION'}]})
        self.assertFalse(success)
        self.assertIn('カーソル',details)
        self.assertIn('CURSOR_OCCLUSION',details)

    def test_no_path_is_not_success(self):
        self.assertFalse(describe_result({'status':'no_path'})[2])


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root=TkinterDnD.Tk()
        except tk.TclError as exc:
            self.skipTest(f'Tk display unavailable: {exc}')
        self.root.withdraw()
        self.tmp=tempfile.TemporaryDirectory(prefix='lumina_gui_')
        self.app=Application(self.root,Path(self.tmp.name)/'results')
        self.root.update()

    def tearDown(self):
        if hasattr(self,'app'):
            self.app.close()
        if hasattr(self,'tmp'):
            self.tmp.cleanup()

    def wait_for_analysis(self):
        deadline=time.monotonic()+15
        while self.app.busy and time.monotonic()<deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy,'Analysis did not complete')
        self.root.update()

    def test_drop_parses_spaces_and_rejects_multiple_files(self):
        path=str(Path(self.tmp.name)/'日本語 folder'/'board image.jpg')
        self.app.on_drop(SimpleNamespace(data='{'+path+'}'))
        self.assertEqual(self.app.path.get(),path)
        self.app.on_drop(SimpleNamespace(data='{a.jpg} {b.jpg}'))
        self.assertIn('1枚',self.app.details.get('1.0','end'))

    def test_nonexistent_input_has_error_screen(self):
        self.app.path.set(str(Path(self.tmp.name)/'missing.jpg'))
        self.app.start()
        self.assertFalse(self.app.busy)
        self.assertIn('解析できません',self.app.status.cget('text'))
        self.assertIsNone(self.app.image)

    def test_corrupt_image_has_error_screen(self):
        source=Path(self.tmp.name)/'broken.png'
        source.write_bytes(b'broken')
        self.app.path.set(str(source))
        self.app.start()
        self.wait_for_analysis()
        self.assertIn('INPUT_READ_ERROR',self.app.details.get('1.0','end'))
        self.assertIsNone(self.app.image)

    @unittest.skipUnless(NORMAL.is_file() and ERROR.is_file(),'External samples unavailable')
    def test_success_then_occlusion_error_clears_old_result(self):
        self.app.path.set(str(NORMAL))
        self.app.start()
        self.assertTrue(self.app.busy)
        self.assertIn('disabled',self.app.analyze_button.state())
        self.wait_for_analysis()
        self.assertIn('16アイコン',self.app.status.cget('text'))
        self.assertIsNotNone(self.app.image)
        self.assertIsNotNone(self.app.photo)
        first=self.app.destination
        self.app.change_zoom(1.25)
        self.app.fit()
        self.app.path.set(str(ERROR))
        self.assertIsNone(self.app.image)
        self.app.start()
        self.wait_for_analysis()
        self.assertIn('CURSOR_OCCLUSION',self.app.details.get('1.0','end'))
        self.assertIsNotNone(self.app.image)
        self.assertNotEqual(first,self.app.destination)
        self.assertTrue((first/'route.png').is_file())
        self.assertTrue((self.app.destination/'error.png').is_file())
        self.assertNotIn('disabled',self.app.analyze_button.state())

    def test_unexpected_worker_error_recovers_controls(self):
        self.app.busy=True
        self.app.messages.put(('failed','output is read-only'))
        self.app.poll()
        self.assertFalse(self.app.busy)
        self.assertIn('output is read-only',self.app.details.get('1.0','end'))
        self.assertNotIn('disabled',self.app.analyze_button.state())


if __name__=='__main__':
    unittest.main()
