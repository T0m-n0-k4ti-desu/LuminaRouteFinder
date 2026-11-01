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

    def test_path_names_and_unknown_are_displayed_without_filters(self):
        result={'status':'ok','max_count':2,'optimal_path_count':2,
                'paths':[[[1,1],[2,1]],[[1,2],[2,1]]],
                'content_types':[['escape_room','element_tiles'],[None,None]]}
        _,details,success=describe_result(result)
        self.assertTrue(success)
        self.assertIn('1. 第1段階・1列目（エスケープルーム）',details)
        self.assertIn('2. 第2段階・1列目',details)
        self.assertNotIn('第2段階・1列目（',details)
        self.assertNotIn('判別不能',details)
        self.assertIn('第1段階・2列目（属性タイル渡り）',describe_result(result,1)[1])

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
        self.app=Application(self.root,Path(self.tmp.name)/'results',settings_path=Path(self.tmp.name)/'gui-settings.json')
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

    def test_long_details_scroll_to_end_and_new_result_resets_to_top(self):
        self.app.set_details('\n'.join(f'Route step {i}' for i in range(500)))
        self.root.update_idletasks()
        command=self.root.tk.splitlist(self.app.view.details_scroll.cget('command'))
        self.root.tk.call(*command,'moveto',1)
        self.root.update_idletasks()
        self.assertGreater(self.app.view.details.yview()[0],0)
        self.assertAlmostEqual(self.app.view.details.yview()[1],1)
        self.assertIn('Route step 499',self.app.view.details.get('1.0','end'))
        self.assertEqual(str(self.app.view.details.cget('state')),'disabled')
        self.app.set_details('New result')
        self.root.update_idletasks()
        self.assertEqual(self.app.view.details.yview()[0],0)

    def test_drop_parses_spaces_and_rejects_multiple_files(self):
        path=str(Path(self.tmp.name)/'日本語 folder'/'board image.jpg')
        self.app.on_drop(SimpleNamespace(data='{'+path+'}'))
        self.assertEqual(self.app.view.path.get(),path)
        self.app.on_drop(SimpleNamespace(data='{a.jpg} {b.jpg}'))
        self.assertIn('1枚',self.app.view.details.get('1.0','end'))

    def test_nonexistent_input_has_error_screen(self):
        self.app.view.path.set(str(Path(self.tmp.name)/'missing.jpg'))
        self.app.start()
        self.assertFalse(self.app.busy)
        self.assertIn('解析できません',self.app.view.status.cget('text'))
        self.assertIsNone(self.app.image)

    def test_corrupt_image_has_error_screen(self):
        source=Path(self.tmp.name)/'broken.png'
        source.write_bytes(b'broken')
        self.app.view.path.set(str(source))
        self.app.start()
        self.wait_for_analysis()
        self.assertIn('INPUT_READ_ERROR',self.app.view.details.get('1.0','end'))
        self.assertIsNone(self.app.image)

    @unittest.skipUnless(NORMAL.is_file() and ERROR.is_file(),'External samples unavailable')
    def test_success_then_occlusion_error_clears_old_result(self):
        self.app.view.path.set(str(NORMAL))
        self.app.start()
        self.assertTrue(self.app.busy)
        self.assertIn('disabled',self.app.view.analyze_button.state())
        self.wait_for_analysis()
        self.assertIn('16アイコン',self.app.view.status.cget('text'))
        self.assertIsNotNone(self.app.image)
        self.assertIsNotNone(self.app.preview.photo)
        first=self.app.destination
        self.app.preview.change_zoom(1.25)
        self.app.preview.fit()
        self.app.view.path.set(str(ERROR))
        self.assertIsNone(self.app.result)
        self.assertIsNotNone(self.app.image)
        self.assertTrue(self.app.preview.showing_input)
        self.app.start()
        self.wait_for_analysis()
        self.assertIn('CURSOR_OCCLUSION',self.app.view.details.get('1.0','end'))
        self.assertIsNotNone(self.app.image)
        self.assertNotEqual(first,self.app.destination)
        self.assertTrue((first/'route.png').is_file())
        self.assertTrue((self.app.destination/'error.png').is_file())
        self.assertNotIn('disabled',self.app.view.analyze_button.state())

    def test_pages_update_image_details_and_button_states(self):
        import numpy as np
        self.app.board=np.zeros((500,260,3),dtype=np.uint8)
        self.app.result={'status':'ok','max_count':2,'optimal_path_count':2,
                         'paths':[[[1,1],[2,1]],[[1,2],[2,2]]],'paths_truncated':False}
        self.app.show_page(0)
        first=self.app.image.copy()
        self.assertEqual(self.app.view.page_text.get(),'候補 1 / 2')
        self.assertIn('disabled',self.app.view.previous_button.state())
        self.app.change_page(1)
        self.assertEqual(self.app.view.page_text.get(),'候補 2 / 2')
        self.assertIn('第1段階・2列目',self.app.view.details.get('1.0','end'))
        self.assertFalse(np.array_equal(first,self.app.image))
        self.assertIn('disabled',self.app.view.next_button.state())
        self.app.change_page(-1)
        self.assertTrue(np.array_equal(first,self.app.image))
        self.app.view.path.set('new.jpg')
        self.assertEqual(self.app.view.page_text.get(),'')
        self.assertIn('disabled',self.app.view.next_button.state())
        self.assertEqual(self.app.view.progress.winfo_manager(),'')

    @unittest.skipUnless(NORMAL.is_file(),'External samples unavailable')
    def test_next_page_fetches_more_and_progress_is_only_visible_while_busy(self):
        source=NORMAL.with_name('TWCI_2026_11_1_1_2_58.jpg')
        if not source.is_file():
            self.skipTest('Sample with multiple optimal paths unavailable')
        self.assertEqual(self.app.view.progress.winfo_manager(),'')
        self.app.view.path.set(str(source))
        self.app.start(limit=1)
        self.assertEqual(self.app.view.progress.winfo_manager(),'pack')
        self.wait_for_analysis()
        self.assertEqual(self.app.view.progress.winfo_manager(),'')
        self.assertEqual(len(self.app.result['paths']),1)
        self.assertTrue(self.app.result['paths_truncated'])
        first=self.app.image.copy()
        self.app.change_page(1)
        self.assertTrue(self.app.busy)
        self.wait_for_analysis()
        self.assertEqual(self.app.page,1)
        self.assertEqual(len(self.app.result['paths']),2)
        self.assertEqual(self.app.view.page_text.get(),'候補 2 / 8')
        self.assertEqual(self.app.view.progress.winfo_manager(),'')
        self.app.change_page(-1)
        import numpy as np
        self.assertTrue(np.array_equal(first,self.app.image))

    def test_clipboard_paste_and_empty_clipboard(self):
        from unittest.mock import patch
        from PIL import Image
        image=Image.new('RGB',(100,80),(20,40,60))
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=image):
            self.assertEqual(self.app.paste_image(),'break')
        saved=Path(self.app.view.path.get())
        self.assertTrue(saved.is_file())
        self.assertEqual(self.app.image.shape[:2],(80,100))
        first=saved
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=image):
            self.app.paste_image()
        self.assertNotEqual(first,Path(self.app.view.path.get()))
        self.assertTrue(first.is_file())
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=None):
            self.app.paste_image()
        self.assertIn('クリップボードに画像がありません',self.app.view.details.get('1.0','end'))

    def test_missing_clipboard_backend_shows_install_help(self):
        from unittest.mock import patch
        self.app.view.path.set('unchanged.jpg')
        with patch('lumina_route_finder.clipboard.get_clipboard_image',
                   side_effect=NotImplementedError('wl-paste or xclip is required')):
            self.assertEqual(self.app.paste_image(), 'break')
        self.assertEqual(self.app.view.path.get(), 'unchanged.jpg')
        self.assertIn('sudo apt install wl-clipboard xclip', self.app.view.details.get('1.0','end'))

    def test_text_paste_does_not_replace_selected_image(self):
        from unittest.mock import patch
        self.app.view.path.set('unchanged.jpg')
        with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=None):
            self.assertIsNone(self.app.paste_image(SimpleNamespace()))
        self.assertEqual(self.app.view.path.get(),'unchanged.jpg')

    @unittest.skipUnless((ROOT/'sample_image/cp_image.jpg').is_file(),'Clipboard example unavailable')
    def test_clipboard_example_analyses_after_paste(self):
        from unittest.mock import patch
        from PIL import Image
        with Image.open(ROOT/'sample_image/cp_image.jpg') as source:
            with patch('lumina_route_finder.clipboard.get_clipboard_image',return_value=source):
                self.app.paste_image()
        self.app.start()
        self.assertIn('disabled',self.app.view.paste_button.state())
        self.wait_for_analysis()
        self.assertIn('11アイコン',self.app.view.status.cget('text'))
        self.assertNotIn('disabled',self.app.view.paste_button.state())

    def test_file_preview_reverse_drag_and_region_analysis(self):
        from unittest.mock import patch
        source=Path(__file__).parent/'fixtures/board_crop.jpg'
        self.app.view.path.set(str(source))
        self.assertTrue(self.app.preview.showing_input)
        self.assertEqual(self.app.image.shape[:2],(496,249))
        self.app.view.selecting.set(True)
        self.app.begin_selection()
        self.app.preview.display_scale=1
        self.app.preview.image_offset=(0,0)
        with patch.object(self.app.view.canvas,'canvasx',side_effect=lambda x:x),patch.object(self.app.view.canvas,'canvasy',side_effect=lambda y:y):
            self.app.preview.selection_start(SimpleNamespace(x=249,y=496))
            self.app.preview.selection_drag(SimpleNamespace(x=0,y=0))
            self.app.preview.selection_end(SimpleNamespace(x=0,y=0))
        self.assertEqual(self.app.region,(0,0,249,496))
        self.app.start()
        self.assertIn('disabled',self.app.view.select_button.state())
        self.wait_for_analysis()
        self.assertEqual(self.app.result['max_count'],18)
        self.assertEqual(self.app.result['input_region'],[0,0,249,496])
        self.assertFalse(self.app.preview.showing_input)
        self.app.show_input()
        self.assertTrue(self.app.preview.showing_input)
        self.app.show_result()
        self.assertFalse(self.app.preview.showing_input)
        self.app.clear_region()
        self.assertIsNone(self.app.region)
        self.assertIsNone(self.app.result)
        self.assertTrue(self.app.preview.showing_input)

    def test_drag_pans_zoomed_input_and_result_without_changing_region(self):
        import numpy as np
        self.app.preview.input_image=np.zeros((500,1000,3),dtype=np.uint8)
        for showing_input in (True,False):
            with self.subTest(showing_input=showing_input):
                self.app.preview.showing_input=showing_input
                self.app.image=self.app.preview.input_image
                self.app.preview.zoom=2
                self.app.region=(50,60,300,400)
                self.app.render()
                self.app.view.canvas.xview_moveto(0)
                self.app.view.canvas.yview_moveto(0)
                before=(self.app.view.canvas.xview()[0],self.app.view.canvas.yview()[0])
                self.app.preview.pointer_start(SimpleNamespace(x=100,y=100))
                self.assertTrue(self.app.preview.panning)
                self.app.preview.pointer_drag(SimpleNamespace(x=40,y=30))
                self.app.preview.pointer_end(SimpleNamespace(x=40,y=30))
                self.assertGreater(self.app.view.canvas.xview()[0],before[0])
                self.assertGreater(self.app.view.canvas.yview()[0],before[1])
                self.assertEqual(self.app.region,(50,60,300,400))
                self.assertFalse(self.app.preview.panning)
                self.assertEqual(self.app.view.canvas.cget('cursor'),'hand2')
                self.app.preview.fit()
                self.assertFalse(self.app.preview.panning)
                self.assertEqual(self.app.view.canvas.xview()[0],0)
                self.assertEqual(self.app.view.canvas.yview()[0],0)

    def test_region_mode_uses_drag_for_selection_and_busy_blocks_panning(self):
        import numpy as np
        self.app.preview.input_image=np.zeros((500,1000,3),dtype=np.uint8)
        self.app.show_input()
        self.app.view.selecting.set(True)
        self.app.preview.zoom=2
        self.app.render()
        before=(self.app.view.canvas.xview(),self.app.view.canvas.yview())
        self.app.preview.pointer_start(SimpleNamespace(x=20,y=20))
        self.assertFalse(self.app.preview.panning)
        self.assertIsNotNone(self.app.preview.drag_start)
        self.app.preview.pointer_drag(SimpleNamespace(x=180,y=180))
        self.assertEqual((self.app.view.canvas.xview(),self.app.view.canvas.yview()),before)
        self.app.preview.pointer_end(SimpleNamespace(x=180,y=180))
        self.assertIsNotNone(self.app.region)
        self.app.view.selecting.set(False)
        self.app.preview.zoom=2
        self.app.render()
        self.app.busy=True
        self.app.preview.pointer_start(SimpleNamespace(x=100,y=100))
        self.assertFalse(self.app.preview.panning)
        self.app.busy=False

    def test_selection_coordinates_account_for_zoom_offsets_and_scroll(self):
        from unittest.mock import patch
        import numpy as np
        self.app.preview.input_image=np.zeros((500,1000,3),dtype=np.uint8)
        self.app.preview.display_scale=.5
        self.app.preview.image_offset=(20,30)
        with patch.object(self.app.view.canvas,'canvasx',return_value=220),patch.object(self.app.view.canvas,'canvasy',return_value=130):
            self.assertEqual(self.app.preview.input_point(SimpleNamespace(x=1,y=1)),(400,200))
        with patch.object(self.app.view.canvas,'canvasx',return_value=-100),patch.object(self.app.view.canvas,'canvasy',return_value=2000):
            self.assertEqual(self.app.preview.input_point(SimpleNamespace(x=1,y=1)),(0,500))

    def test_filter_options_default_off_and_combined_analysis(self):
        from lumina_route_finder.contents import CONTENT_NAMES
        sample=Path(__file__).resolve().parents[1]/'docs/images/sample_image.jpg'
        self.assertFalse(self.app.view.avoid_repeated.get())
        self.assertFalse(self.app.view.exclude_enabled.get())
        self.assertEqual(self.app.view.content_list.cget('state'),'disabled')
        self.app.view.path.set(str(sample))
        self.app.view.avoid_repeated.set(True)
        self.app.view.exclude_enabled.set(True)
        self.app.options_changed()
        self.app.view.content_list.selection_set(list(CONTENT_NAMES).index('boss_mutation'))
        self.app.start(limit=1)
        self.assertIn('disabled',self.app.view.repeat_check.state())
        self.wait_for_analysis()
        self.assertEqual(self.app.result['status'],'ok')
        self.assertEqual(self.app.result['filters'],{'avoid_repeated':True,'excluded_types':['boss_mutation']})
        self.assertIn(self.app.destination,self.app.session_outputs.directories)
        self.assertIn('同じコンテンツの連続を禁止',self.app.view.details.get('1.0','end'))
        self.assertIn('ボス変異戦闘',self.app.view.details.get('1.0','end'))
        if self.app.result['paths_truncated']:
            self.app.change_page(1)
            self.wait_for_analysis()
            self.assertEqual(self.app.page,1)
            self.assertTrue(self.app.result['filters']['avoid_repeated'])
            self.assertEqual(self.app.result['filters']['excluded_types'],['boss_mutation'])
        self.app.view.exclude_enabled.set(False)
        self.app.options_changed()
        self.assertIsNone(self.app.result)
        self.assertEqual(self.app.view.content_list.cget('state'),'disabled')
        self.app.view.avoid_repeated.set(False)
        self.app.options_changed()
        self.app.start()
        self.wait_for_analysis()
        self.assertEqual(self.app.result['status'],'ok')
        self.assertNotIn('filters',self.app.result)

    def test_empty_exclusion_selection_requires_target(self):
        self.app.view.path.set(str(Path(__file__).resolve().parents[1]/'docs/images/sample_image.jpg'))
        self.app.view.exclude_enabled.set(True)
        self.app.options_changed()
        self.app.start()
        self.assertFalse(self.app.busy)
        self.assertIn('1つ以上',self.app.view.details.get('1.0','end'))

    def test_cleanup_checkbox_default_and_disable_persists(self):
        from lumina_route_finder.session import load_cleanup_setting
        self.assertTrue(self.app.delete_outputs.get())
        self.app.delete_outputs.set(False)
        self.app.save_settings()
        self.assertFalse(load_cleanup_setting(self.app.settings_path))
        directory=self.app.output_root/'current'
        directory.mkdir(parents=True)
        (directory/'route.png').write_bytes(b'keep')
        self.app.session_outputs.add_directory(directory)
        self.app.close()
        self.assertTrue((directory/'route.png').exists())

    def test_close_waits_for_worker_and_cleans_even_unpolled_results(self):
        import threading
        from unittest.mock import patch
        with patch('lumina_route_finder.ui.controller.analyze_file') as analyze:
            entered=threading.Event();release=threading.Event()
            def delayed(source,root,limit,region,on_created,**options):
                self.assertIs(options.pop('cache'),self.app.analysis_cache)
                self.assertIs(options.pop('cancel'),self.app.cancel_event)
                self.assertTrue(callable(options.pop('progress')))
                self.assertEqual(options.pop('objective'),'count')
                self.assertEqual(options.pop('weights'),{})
                self.assertEqual(options,{'avoid_repeated':True,'excluded_types':('boss_mutation',),'fallback_priority':'stage'})
                destination=Path(root)/'unpolled'
                destination.mkdir(parents=True)
                on_created(destination)
                entered.set()
                release.wait(5)
                (destination/'route.png').write_bytes(b'result')
                return {'status':'no_path'},destination,None
            analyze.side_effect=delayed
            from lumina_route_finder.contents import CONTENT_NAMES
            self.app.view.path.set(str(Path(__file__).resolve().parents[1]/'docs/images/sample_image.jpg'))
            self.app.view.avoid_repeated.set(True)
            self.app.view.exclude_enabled.set(True)
            self.app.options_changed()
            self.app.view.content_list.selection_set(list(CONTENT_NAMES).index('boss_mutation'))
            self.app.start()
            self.assertTrue(entered.wait(2))
            self.app.close()
            self.assertFalse(self.app.closed)
            self.assertTrue(self.app.closing)
            self.assertIn('disabled',self.app.view.repeat_check.state())
            self.assertIn('disabled',self.app.view.exclude_check.state())
            release.set()
            deadline=time.monotonic()+5
            while not self.app.closed and time.monotonic()<deadline:
                self.root.update()
                time.sleep(.01)
            self.assertTrue(self.app.closed)
            self.assertFalse((self.app.output_root/'unpolled').exists())

    def test_close_cancels_pending_preview_render(self):
        self.app.preview.schedule_render()
        self.assertIsNotNone(self.app.preview.resize_id)
        self.app.close()
        self.assertTrue(self.app.closed)
        self.assertIsNone(self.app.preview.resize_id)

    def test_expected_worker_error_preserves_its_code_and_message(self):
        from unittest.mock import patch
        from lumina_route_finder.errors import RecognitionError, ErrorCode, issue
        self.app.busy=True
        with patch('lumina_route_finder.ui.controller.analyze_file',
                   side_effect=RecognitionError([issue(ErrorCode.BOARD_NOT_FOUND,'header missing')])):
            self.app.worker(Path('source.jpg'),20,None)
        self.app.poll()
        details=self.app.view.details.get('1.0','end')
        self.assertIn('盤面を検出できません',details)
        self.assertIn('header missing',details)
        self.assertFalse(self.app.busy)
        self.assertNotIn('disabled',self.app.view.analyze_button.state())

    def test_unexpected_worker_error_recovers_controls(self):
        self.app.busy=True
        self.app.messages.put(('failed',[{'code':'OUTPUT_WRITE_ERROR','message':'output is read-only'}]))
        self.app.poll()
        self.assertFalse(self.app.busy)
        self.assertIn('output is read-only',self.app.view.details.get('1.0','end'))
        self.assertNotIn('disabled',self.app.view.analyze_button.state())


if __name__=='__main__':
    unittest.main()
