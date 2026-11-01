import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lumina_route_finder.analysis_session import BoardSnapshot,AnalysisCache
from lumina_route_finder.recognition_review import RecognitionEditor,render_recognition
from lumina_route_finder.analysis import run_image
from lumina_route_finder.errors import RecognitionError,issue,ErrorCode
ROOT=Path(__file__).resolve().parents[1]
def snapshot():
    return BoardSnapshot(np.zeros((500,260,3),dtype=np.uint8),(0,0),[],[{'from':(0,0),'to':(1,0),'state':'uncertain','dark_pixels':4}],1,{(r,c):'escape_room' for r in range(10) for c in range(5)},[],confirmed=False,pending_edges=[((0,0),(1,0))])
class ReviewTests(unittest.TestCase):
    def test_explicit_confirmation_validation_undo_and_original_are_independent(self):
        original=snapshot();editor=RecognitionEditor(original)
        with self.assertRaises(ValueError):editor.confirm(True)
        for edge in [((1,0),(0,0)),((0,0),(2,0)),((0,0),(0,2))]:
            with self.assertRaises(ValueError):editor.set_edge(*edge,True)
        editor.set_edge((0,0),(1,0),True);editor.set_label((0,0),'boss_mutation')
        self.assertEqual(original.labels[(0,0)],'escape_room');self.assertFalse(original.edges)
        editor.undo();self.assertEqual(editor.snapshot.labels[(0,0)],'escape_room')
        with self.assertRaises(ValueError):editor.confirm(False)
        accepted=editor.confirm(True);self.assertTrue(accepted.confirmed)
        self.assertTrue(accepted.corrections);self.assertEqual(render_recognition(accepted).shape,(1000,520,3))
        editor.reset();self.assertFalse(editor.snapshot.confirmed)
    def test_ambiguous_edges_stay_errors_until_user_confirmation_then_reuse(self):
        cache=AnalysisCache();snap=snapshot();error=RecognitionError([issue(ErrorCode.AMBIGUOUS_CONNECTION,'uncertain')],snap.board)
        labels=snap.labels
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch('lumina_route_finder.analysis.recognize',side_effect=[error,(snap.board,(0,0),[],snap.diagnostics,1)]) as recognize,patch('lumina_route_finder.contents.classify_contents',return_value=(labels,[])):
                result=run_image(ROOT/'docs/images/sample_image.jpg',root/'a',cache=cache)
            self.assertEqual(result['status'],'error');self.assertFalse(cache.snapshot.confirmed)
            result=run_image(ROOT/'docs/images/sample_image.jpg',root/'b',cache=cache)
            self.assertEqual(result['status'],'error')
            editor=RecognitionEditor(cache.snapshot,cache.original);editor.set_edge((0,0),(1,0),False)
            cache.snapshot=editor.confirm(True)
            with patch('lumina_route_finder.analysis.recognize',side_effect=AssertionError('should reuse')):
                result=run_image(ROOT/'docs/images/sample_image.jpg',root/'c',cache=cache)
            self.assertEqual(result['status'],'partial');self.assertTrue(result['manual_corrections'])
    def test_occluded_boards_cannot_enter_correction_mode(self):
        cache=AnalysisCache()
        with tempfile.TemporaryDirectory() as temp,patch('lumina_route_finder.analysis.recognize',side_effect=RecognitionError([issue(ErrorCode.CURSOR_OCCLUSION,'cursor')])):
            result=run_image(ROOT/'docs/images/sample_image.jpg',Path(temp),cache=cache)
        self.assertEqual(result['status'],'error');self.assertIsNone(cache.snapshot)
    def test_inspector_widgets_can_show_and_edit_a_real_snapshot(self):
        import tkinter as tk
        from tkinterdnd2 import TkinterDnD
        from lumina_route_finder.ui.controller import Application
        from lumina_route_finder.ui.recognition_inspector import RecognitionInspector
        try:root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw()
        with tempfile.TemporaryDirectory() as temp:
            app=Application(root,Path(temp)/'outputs',settings_path=Path(temp)/'settings.json')
            try:
                app.analysis_cache.put(('test',),snapshot());dialog=RecognitionInspector(app);root.update()
                self.assertEqual(len(dialog.nodes.get_children()),50)
                dialog.nodes.selection_set('0,0');dialog.node_selected();dialog.kind.set('ボス変異戦闘');dialog.change_kind()
                self.assertEqual(dialog.editor.snapshot.labels[(0,0)],'boss_mutation')
                dialog.undo();self.assertEqual(dialog.editor.snapshot.labels[(0,0)],'escape_room')
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
