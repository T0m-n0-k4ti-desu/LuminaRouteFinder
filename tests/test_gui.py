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

    def test_pages_update_image_details_and_button_states(self):
        import numpy as np
        self.app.board=np.zeros((500,260,3),dtype=np.uint8)
        self.app.result={'status':'ok','max_count':2,'optimal_path_count':2,
                         'paths':[[[1,1],[2,1]],[[1,2],[2,2]]],'paths_truncated':False}
        self.app.show_page(0)
        first=self.app.image.copy()
        self.assertEqual(self.app.page_text.get(),'候補 1 / 2')
        self.assertIn('disabled',self.app.previous_button.state())
        self.app.change_page(1)
        self.assertEqual(self.app.page_text.get(),'候補 2 / 2')
        self.assertIn('第1段階・2列目',self.app.details.get('1.0','end'))
        self.assertFalse(np.array_equal(first,self.app.image))
        self.assertIn('disabled',self.app.next_button.state())
        self.app.change_page(-1)
        self.assertTrue(np.array_equal(first,self.app.image))
        self.app.path.set('new.jpg')
        self.assertEqual(self.app.page_text.get(),'')
        self.assertIn('disabled',self.app.next_button.state())
        self.assertEqual(self.app.progress.winfo_manager(),'')

    @unittest.skipUnless(NORMAL.is_file(),'External samples unavailable')
    def test_next_page_fetches_more_and_progress_is_only_visible_while_busy(self):
        source=NORMAL.with_name('TWCI_2026_11_1_1_2_58.jpg')
        if not source.is_file():
            self.skipTest('Sample with multiple optimal paths unavailable')
        self.assertEqual(self.app.progress.winfo_manager(),'')
        self.app.path.set(str(source))
        self.app.start(limit=1)
        self.assertEqual(self.app.progress.winfo_manager(),'pack')
        self.wait_for_analysis()
        self.assertEqual(self.app.progress.winfo_manager(),'')
        self.assertEqual(len(self.app.result['paths']),1)
        self.assertTrue(self.app.result['paths_truncated'])
        first=self.app.image.copy()
        self.app.change_page(1)
        self.assertTrue(self.app.busy)
        self.wait_for_analysis()
        self.assertEqual(self.app.page,1)
        self.assertEqual(len(self.app.result['paths']),2)
        self.assertEqual(self.app.page_text.get(),'候補 2 / 8')
        self.assertEqual(self.app.progress.winfo_manager(),'')
        self.app.change_page(-1)
        import numpy as np
        self.assertTrue(np.array_equal(first,self.app.image))

    def test_clipboard_paste_and_empty_clipboard(self):
        from unittest.mock import patch
        from PIL import Image
        image=Image.new('RGB',(100,80),(20,40,60))
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=image):
            self.assertEqual(self.app.paste_image(),'break')
        saved=Path(self.app.path.get())
        self.assertTrue(saved.is_file())
        self.assertEqual(self.app.image.shape[:2],(80,100))
        first=saved
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=image):
            self.app.paste_image()
        self.assertNotEqual(first,Path(self.app.path.get()))
        self.assertTrue(first.is_file())
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=None):
            self.app.paste_image()
        self.assertIn('クリップボードに画像がありません',self.app.details.get('1.0','end'))

    def test_text_paste_does_not_replace_selected_image(self):
        from unittest.mock import patch
        self.app.path.set('unchanged.jpg')
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=None):
            self.assertIsNone(self.app.paste_image(SimpleNamespace()))
        self.assertEqual(self.app.path.get(),'unchanged.jpg')

    @unittest.skipUnless((ROOT/'sample_image/cp_image.jpg').is_file(),'Clipboard example unavailable')
    def test_clipboard_example_analyses_after_paste(self):
        from unittest.mock import patch
        from PIL import Image
        with Image.open(ROOT/'sample_image/cp_image.jpg') as source:
            with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=source):
                self.app.paste_image()
        self.app.start()
        self.assertIn('disabled',self.app.paste_button.state())
        self.wait_for_analysis()
        self.assertIn('11アイコン',self.app.status.cget('text'))
        self.assertNotIn('disabled',self.app.paste_button.state())

    def test_unexpected_worker_error_recovers_controls(self):
        self.app.busy=True
        self.app.messages.put(('failed','output is read-only'))
        self.app.poll()
        self.assertFalse(self.app.busy)
        self.assertIn('output is read-only',self.app.details.get('1.0','end'))
        self.assertNotIn('disabled',self.app.analyze_button.state())


if __name__=='__main__':
    unittest.main()
