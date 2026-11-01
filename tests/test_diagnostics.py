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
                target=next(i for i,r in enumerate(dialog.rows) if not r['options']['exclude_enabled'])
                dialog.table.selection_set(str(target))
                with patch.object(app,'start') as start:dialog.apply();start.assert_called_once()
                self.assertFalse(app.view.exclude_enabled.get())
            finally:root.update_idletasks();app.close()
if __name__=='__main__':unittest.main()
