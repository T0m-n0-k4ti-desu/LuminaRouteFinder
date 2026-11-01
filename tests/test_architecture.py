"""Boundary checks for independently changeable modules, using fresh interpreters."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ArchitectureTests(unittest.TestCase):
    def check_imports(self, imports, forbidden):
        script=imports+'\nimport sys\n'+'\n'.join(
            f"assert not any(n == {name!r} or n.startswith({name+'.'!r}) for n in sys.modules), {name!r}"
            for name in forbidden)
        result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_domain_has_no_image_gui_or_storage_dependencies(self):
        self.check_imports('from lumina_route_finder.domain import solver, catalog, geometry',
                          ['cv2','numpy','tkinter','lumina_route_finder.settings','lumina_route_finder.ui'])

    def test_settings_and_presentation_do_not_load_recognizer(self):
        self.check_imports('from lumina_route_finder import settings\nfrom lumina_route_finder.ui import presentation',
                          ['cv2','numpy','tkinter','lumina_route_finder.recognize'])

    def test_analysis_and_cli_do_not_load_gui(self):
        self.check_imports('from lumina_route_finder import analysis, cli',
                          ['tkinter','tkinterdnd2','lumina_route_finder.ui'])

    def test_original_helper_imports_remain_compatible(self):
        from lumina_route_finder import __main__, analysis, image_io, recognize, solver, session, settings
        from lumina_route_finder.domain import solver as domain_solver
        self.assertIs(__main__.run_image,analysis.run_image)
        self.assertIs(__main__.write_image,image_io.write_image)
        self.assertIs(recognize.read_image,image_io.read_image)
        self.assertIs(solver.solve,domain_solver.solve)
        self.assertIs(session.load_settings,settings.load_settings)


    def test_review_data_operations_do_not_load_image_or_gui_libraries(self):
        self.check_imports('from lumina_route_finder.application.review import RecognitionEditor',
                          ['cv2','numpy','tkinter','lumina_route_finder.rendering'])

    def test_public_facades_reference_canonical_modules(self):
        import importlib
        pairs = {'analysis':'application.analysis', 'recognize':'recognition.connections',
                 'settings':'storage.settings', 'session':'storage.session_outputs',
                 'image_io':'storage.images', 'errors':'shared.errors',
                 'error_messages':'shared.messages', 'cli':'application.cli'}
        for old, new in pairs.items():
            with self.subTest(module=old):
                self.assertIs(importlib.import_module('lumina_route_finder.'+old),
                              importlib.import_module('lumina_route_finder.'+new))

    def test_relocated_modules_keep_source_data_paths(self):
        from lumina_route_finder.shared.paths import ASSETS
        from lumina_route_finder.storage.settings import default_settings_path
        self.assertEqual(ASSETS, ROOT/'lumina_route_finder'/'assets')
        self.assertTrue(ASSETS.is_dir())
        self.assertEqual(default_settings_path(), ROOT/'gui-settings.json')


if __name__=='__main__':
    unittest.main()
