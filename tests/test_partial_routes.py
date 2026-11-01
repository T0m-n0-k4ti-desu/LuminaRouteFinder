import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch
import numpy as np
from tkinterdnd2 import TkinterDnD
from lumina_route_finder.solver import solve
from lumina_route_finder.gui import Application,describe_result
from lumina_route_finder.session import load_settings,save_settings,migrate_cleanup_setting,save_cleanup_setting
from lumina_route_finder.contents import CONTENT_NAMES

REPO=Path(__file__).resolve().parents[1]


class PartialSolverTests(unittest.TestCase):
    def test_stage_and_count_choose_different_partial_routes(self):
        nodes=[(r,c) for r in range(4) for c in range(5)]
        edges=[((0,c),(0,c+1)) for c in range(3)]+[((0,4),(1,4)),((1,4),(2,4))]
        stage=solve(nodes,edges,fallback_priority='stage')
        count=solve(nodes,edges,fallback_priority='count',limit=1)
        self.assertEqual((stage['status'],stage['reached_stage'],stage['max_count']),('partial',3,3))
        self.assertEqual((count['status'],count['reached_stage'],count['max_count']),('partial',1,4))
        self.assertEqual(count['optimal_path_count'],2)
        self.assertTrue(count['paths_truncated'])
        self.assertFalse(stage['goal_reached'])

    def test_goal_route_always_wins_over_longer_incomplete_route(self):
        nodes=[(r,c) for r in range(4) for c in range(6)]
        edges=[((0,c),(0,c+1)) for c in range(4)]+[((r,5),(r+1,5)) for r in range(3)]
        for priority in ('stage','count'):
            result=solve(nodes,edges,fallback_priority=priority)
            self.assertEqual((result['status'],result['max_count'],result['reached_stage']),('ok',4,4))
            self.assertTrue(result['goal_reached'])

    def test_blocked_starts_and_disabled_fallback(self):
        nodes=[(0,0),(1,0)]
        self.assertEqual(solve(nodes,[],fallback_priority=None)['status'],'no_path')
        for priority in ('stage','count'):
            result=solve(nodes,[],fallback_priority=priority,node_types={(0,0):'a',(1,0):'b'},excluded_types=['a'])
            self.assertEqual(result['status'],'no_path')
        with self.assertRaises(ValueError):solve(nodes,[],fallback_priority='invalid')

    def test_both_priorities_match_independent_exhaustive_search(self):
        rng=random.Random(930)
        nodes=[(r,c) for r in range(4) for c in range(3)]
        candidates=[(u,v) for u in nodes for v in nodes if (u[0]==v[0] and v[1]==u[1]+1) or (v[0]==u[0]+1 and abs(v[1]-u[1])<=1)]
        for _ in range(80):
            edges=[e for e in candidates if rng.random()<.32]
            types={n:rng.choice(('a','b','c')) for n in nodes}
            for filtered in (False,True):
                allowed={n for n in nodes if not filtered or types[n]!='c'}
                adj={n:set() for n in allowed}
                for u,v in edges:
                    if u not in allowed or v not in allowed or (filtered and types[u]==types[v]):continue
                    adj[u].add(v)
                    if u[0]==v[0]:adj[v].add(u)
                all_paths=[]
                def walk(path):
                    all_paths.append(tuple(path))
                    for nxt in adj[path[-1]]:
                        if nxt not in path:walk(path+[nxt])
                for n in allowed:
                    if n[0]==0:walk([n])
                goals=[p for p in all_paths if p[-1][0]==3]
                for priority in ('stage','count'):
                    pool=goals or all_paths
                    score=(lambda p:(len(p),)) if goals else ((lambda p:(p[-1][0],len(p))) if priority=='stage' else (lambda p:(len(p),p[-1][0])))
                    best=max(map(score,pool),default=None)
                    expected={p for p in pool if score(p)==best}
                    result=solve(nodes,edges,limit=10000,fallback_priority=priority,node_types=types,excluded_types=['c'] if filtered else (),avoid_repeated=filtered)
                    self.assertEqual({tuple(p) for p in result['paths']},expected)
                    self.assertEqual(result['optimal_path_count'],len(expected))
                    self.assertEqual(result['status'],'ok' if goals else ('partial' if expected else 'no_path'))

    def test_cli_reports_partial_separately_and_can_disable_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/'graph.json';source.write_text(json.dumps({'nodes':[[1,1],[2,1]],'edges':[]}),encoding='utf-8')
            for priority,status in [('stage','partial'),('count','partial'),('none','no_path')]:
                out=root/priority
                process=subprocess.run([sys.executable,'-m','lumina_route_finder',str(source),'--graph','--fallback-priority',priority,'--output-dir',str(out)],cwd=REPO,capture_output=True)
                self.assertEqual(process.returncode,1)
                self.assertEqual(json.loads((out/'result.json').read_text())['status'],status)


class SettingsTests(unittest.TestCase):
    def test_defaults_validation_and_unknown_key_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'settings.json'
            defaults=load_settings(path)
            self.assertEqual(defaults['fallback_priority'],'stage')
            self.assertFalse(defaults['avoid_repeated'])
            path.write_text(json.dumps({'delete_outputs_on_exit':False,'avoid_repeated':True,'exclude_enabled':'false','excluded_types':['escape_room','unknown','escape_room'],'fallback_priority':'invalid','initial_path_limit':True,'future_option':7}),encoding='utf-8')
            settings=load_settings(path)
            self.assertFalse(settings['delete_outputs_on_exit'])
            self.assertTrue(settings['avoid_repeated'])
            self.assertFalse(settings['exclude_enabled'])
            self.assertEqual(settings['excluded_types'],['escape_room'])
            self.assertEqual(settings['fallback_priority'],'stage')
            self.assertEqual(settings['initial_path_limit'],20)
            save_settings(path,settings)
            save_cleanup_setting(path,True)
            stored=json.loads(path.read_text())
            self.assertEqual(stored['future_option'],7)
            self.assertTrue(stored['avoid_repeated'])
            for limit in (0,-1,1001,'20'):
                save_settings(path,{'initial_path_limit':limit})
                self.assertEqual(load_settings(path)['initial_path_limit'],20)

    def test_legacy_settings_migrate_all_search_options(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'outputs/gui/gui-settings.json';new=root/'gui-settings.json'
            values={'delete_outputs_on_exit':False,'avoid_repeated':True,'exclude_enabled':True,'excluded_types':['escape_room'],'fallback_priority':'count','initial_path_limit':3}
            save_settings(old,values)
            migrate_cleanup_setting(new,old)
            self.assertEqual(load_settings(new),values)
            self.assertFalse(old.exists())
            save_settings(old,dict(values,fallback_priority='stage'))
            migrate_cleanup_setting(new,old)
            self.assertEqual(load_settings(new)['fallback_priority'],'count')


class PartialGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.root=TkinterDnD.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        self.root.withdraw()
        self.temp=tempfile.TemporaryDirectory()
        self.root_path=Path(self.temp.name)
        self.settings=self.root_path/'gui-settings.json'
        self.app=Application(self.root,self.root_path/'outputs',settings_path=self.settings)
        self.root.update()

    def tearDown(self):
        if hasattr(self,'app'):self.app.close()
        if hasattr(self,'temp'):self.temp.cleanup()

    def wait(self):
        deadline=time.monotonic()+15
        while self.app.busy and time.monotonic()<deadline:
            self.root.update();time.sleep(.01)
        self.assertFalse(self.app.busy)
        self.root.update()

    def test_search_settings_survive_restart_and_disabled_exclusions(self):
        self.app.avoid_repeated.set(True)
        self.app.exclude_enabled.set(True)
        self.app.options_changed()
        index=list(CONTENT_NAMES).index('escape_room')
        self.app.content_list.selection_set(index)
        self.app.fallback_priority.set('通過アイコン数を優先')
        self.app.initial_path_limit=3
        self.app.options_changed()
        self.assertTrue(load_settings(self.settings)['exclude_enabled'])
        self.app.exclude_enabled.set(False)
        self.app.options_changed()
        self.app.close()
        self.root=TkinterDnD.Tk();self.root.withdraw()
        self.app=Application(self.root,self.root_path/'outputs',settings_path=self.settings)
        self.root.update()
        self.assertTrue(self.app.avoid_repeated.get())
        self.assertFalse(self.app.exclude_enabled.get())
        self.assertEqual(self.app.content_list.curselection(),(index,))
        self.assertEqual(self.app.fallback_priority.get(),'通過アイコン数を優先')
        self.assertEqual(self.app.initial_path_limit,3)
        self.app.delete_outputs.set(False);self.app.save_settings()
        self.assertEqual(load_settings(self.settings)['excluded_types'],['escape_room'])

    def test_partial_routes_have_preview_paging_and_priority_preserved(self):
        board=np.zeros((500,260,3),dtype=np.uint8)
        labels={(r,c):None for r in range(10) for c in range(5)}
        self.app.path.set(str(REPO/'docs/images/sample_image.jpg'))
        self.app.fallback_priority.set('通過アイコン数を優先')
        self.app.options_changed()
        with patch('lumina_route_finder.__main__.recognize',return_value=(board,(0,0),[],[],1)),patch('lumina_route_finder.contents.classify_contents',return_value=(labels,[])):
            self.app.initial_path_limit=1
            self.app.start();self.wait()
            self.assertEqual(len(self.app.result["paths"]),1)
            self.assertEqual(self.app.result['status'],'partial')
            self.assertEqual(self.app.result['reached_stage'],1)
            self.assertIn('ゴール未到達',self.app.status.cget('text'))
            self.assertIn('通過アイコン数を優先',self.app.details.get('1.0','end'))
            self.assertIsNotNone(self.app.photo)
            self.assertTrue((self.app.destination/'route.png').exists())
            self.app.change_page(1);self.wait()
            self.assertEqual(self.app.page,1)
            self.assertEqual(self.app.result['fallback_priority'],'count')
            self.assertEqual(self.app.result['optimal_path_count'],5)
            self.app.show_input();self.app.show_result()
            self.assertFalse(self.app.showing_input)
        title,_,usable=describe_result(self.app.result)
        self.assertTrue(usable)
        self.assertNotIn('解析完了',title)


if __name__=='__main__':unittest.main()
