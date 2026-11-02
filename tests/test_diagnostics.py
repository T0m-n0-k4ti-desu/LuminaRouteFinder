import copy,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from lumina_route_finder.domain.diagnostics import diagnose,compare_relaxations,relaxation_variants
from lumina_route_finder.domain.jobs import AnalysisCancelled
from lumina_route_finder.rendering.diagnostics import render_diagnostics
class DiagnosticTests(unittest.TestCase):
    def test_reachability_filtered_frontier_and_relaxation_do_not_mutate_options(self):
        nodes=[(0,0),(1,0),(2,0)];edges=[(nodes[0],nodes[1]),(nodes[1],nodes[2])];labels={nodes[0]:'a',nodes[1]:'b',nodes[2]:'a'}
        options={'exclude_enabled':True,'excluded_types':['b'],'avoid_repeated':True,'fallback_priority':'stage','objective':'count_then_weight','weights':{'a':2}}
        before=copy.deepcopy(options);d=diagnose(nodes,edges,labels,options)
        self.assertEqual(d['furthest_stage'],1);self.assertEqual(d['frontier_edges'][0]['reason'],'excluded')
        rows=compare_relaxations(nodes,edges,labels,options)
        self.assertEqual(options,before);self.assertEqual(rows[0]['result']['status'],'partial')
        self.assertTrue(any(r['result']['status']=='ok' for r in rows))
        self.assertTrue(all(r['options']['weights']==options['weights'] for r in rows))
        self.assertEqual(render_diagnostics(np.zeros((500,260,3),dtype=np.uint8),d).shape,(1000,520,3))
        event=threading.Event();event.set()
        with self.assertRaises(AnalysisCancelled):compare_relaxations(nodes,edges,labels,options,event)
    def test_unknown_types_and_excluded_starts(self):
        nodes=[(0,0),(1,0)]
        with self.assertRaises(ValueError):diagnose(nodes,[],dict.fromkeys(nodes),{'avoid_repeated':True})
        d=diagnose(nodes,[],{n:'a' for n in nodes},{'exclude_enabled':True,'excluded_types':['a']})
        self.assertEqual(d['furthest_stage'],0);self.assertFalse(d['reachable_nodes'])
    def test_changed_search_options_restart_comparison(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from lumina_route_finder.ui.diagnostics_dialog import DiagnosticsDialog
        options={'objective':'count','weights':{},'avoid_repeated':False,'exclude_enabled':False,'excluded_types':[],'fallback_priority':'stage'}
        for change in ({'objective':'weight'},{'weights':{'escape_room':99}},{'avoid_repeated':True},
                       {'exclude_enabled':True},{'excluded_types':['escape_room']},{'fallback_priority':'count'}):
            with self.subTest(change=change):
                dialog=DiagnosticsDialog.__new__(DiagnosticsDialog)
                dialog.options=copy.deepcopy(options);dialog.key='image';dialog.revision=1
                dialog.window=Mock();dialog.table=Mock();dialog.table.selection.return_value=('0',)
                dialog.rows=[{'options':options,'result':{'status':'ok'}}]
                dialog.close=Mock()
                dialog.app=SimpleNamespace(busy=False,closing=False,current_search=Mock(return_value=dict(options,**change)),
                    apply_search=Mock(),start=Mock(),analysis_cache=SimpleNamespace(key='image',revision=1,signature=Mock(return_value='image')),
                    view=SimpleNamespace(path=Mock()),region=None)
                with patch.object(dialog,'restart_comparison') as restart:
                    dialog.apply();restart.assert_called_once()
                dialog.app.apply_search.assert_not_called();dialog.app.start.assert_not_called();dialog.close.assert_not_called()

    def test_changed_image_runs_analysis_before_recomparison(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from lumina_route_finder.ui.diagnostics_dialog import DiagnosticsDialog
        dialog=DiagnosticsDialog.__new__(DiagnosticsDialog)
        dialog.closed=False;dialog.cancel=threading.Event();dialog.poll_id=None
        dialog.window=Mock();dialog.table=Mock();dialog.table.get_children.return_value=();dialog.status=Mock();dialog.apply_button=Mock()
        dialog.app=SimpleNamespace(busy=False,closing=False,start=Mock(),region=None,
            view=SimpleNamespace(path=Mock()),analysis_cache=SimpleNamespace(
                signature=Mock(return_value='new'),key='old',snapshot=None))
        dialog.refresh_image();dialog.app.start.assert_called_once()
        self.assertEqual(dialog.rows,[]);dialog.apply_button.configure.assert_called_with(state='disabled')
        with patch.object(dialog,'restart_comparison') as restart:
            dialog.app.busy=True;dialog.wait_for_analysis();restart.assert_not_called()
            dialog.app.busy=False;dialog.wait_for_analysis();restart.assert_not_called()
            dialog.app.analysis_cache.key='new'
            dialog.app.analysis_cache.snapshot=SimpleNamespace(confirmed=True)
            dialog.wait_for_analysis();restart.assert_called_once()

    def test_dialog_completes_without_applying_and_can_apply_explicit_choice(self):
        import tkinter as tk
        from tkinterdnd2 import TkinterDnD
        from lumina_route_finder.ui.controller import Application
        from lumina_route_finder.ui.diagnostics_dialog import DiagnosticsDialog
        from lumina_route_finder.analysis import run_image
        try:root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw()
        with tempfile.TemporaryDirectory() as temp:
            app=Application(root,Path(temp)/'outputs',settings_path=Path(temp)/'settings.json')
            try:
                source=Path(__file__).resolve().parents[1]/'docs/images/sample_image.jpg';app.path.set(str(source))
                run_image(source,Path(temp)/'recognition',cache=app.analysis_cache)
                app.apply_search({'exclude_enabled':True,'excluded_types':['wheel_of_fate'],'fallback_priority':'stage'})
                before=app.current_search();dialog=DiagnosticsDialog(app)
                deadline=time.monotonic()+5
                while not dialog.rows and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertTrue(dialog.rows);self.assertEqual(app.current_search(),before)
                dialog.table.selection_set('0')
                changed=dict(before,objective='weight',weights={'escape_room':3})
                app.apply_search(changed)
                with patch.object(app,'start') as start:
                    dialog.apply();start.assert_not_called()
                self.assertEqual(dialog.rows,[])
                self.assertEqual(str(dialog.apply_button['state']),'disabled')
                self.assertIn('再比較',dialog.status['text'])
                deadline=time.monotonic()+5
                while not dialog.rows and time.monotonic()<deadline:root.update();time.sleep(.01)
                self.assertTrue(dialog.rows);self.assertEqual(dialog.options,app.current_search())
                self.assertTrue(all(row['options']['weights']=={'escape_room':3} for row in dialog.rows))
                target=next(i for i,r in enumerate(dialog.rows) if not r['options']['exclude_enabled'])
                dialog.table.selection_set(str(target))
                with patch.object(app,'start') as start:dialog.apply();start.assert_called_once()
                self.assertFalse(app.view.exclude_enabled.get())
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
