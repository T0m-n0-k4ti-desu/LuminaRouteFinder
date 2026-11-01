import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec=importlib.util.spec_from_file_location('package_release',Path(__file__).resolve().parents[1]/'tools/release/package.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PortablePackageTests(unittest.TestCase):
    def test_zip_contains_only_executable_and_valid_default_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            exe=root/'app.exe';exe.write_bytes(b'MZ-example')
            config=Path(__file__).resolve().parents[1]/'config/gui-settings.json'
            archive=module.create_portable_zip(exe,config,root/'portable.zip')
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()),{'LuminaRouteFinder.exe','gui-settings.json'})
                self.assertEqual(bundle.read('LuminaRouteFinder.exe'),b'MZ-example')
                self.assertTrue(json.loads(bundle.read('gui-settings.json'))['delete_outputs_on_exit'])


if __name__=='__main__':
    unittest.main()
