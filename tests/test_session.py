from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lumina_route_finder.session import SessionOutputs,load_cleanup_setting,save_cleanup_setting


class SessionTests(unittest.TestCase):
    def test_default_settings_beside_executable_not_working_or_extraction_directory(self):
        import sys
        from lumina_route_finder.session import default_settings_path
        with tempfile.TemporaryDirectory() as temp:
            exe=Path(temp)/'portable/LuminaRouteFinder.exe'
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(exe)):
                self.assertEqual(default_settings_path(),exe.resolve().parent/'gui-settings.json')

    def test_legacy_setting_migrates_and_existing_new_setting_wins(self):
        from lumina_route_finder.session import migrate_cleanup_setting
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);legacy=root/'outputs/gui/gui-settings.json';new=root/'gui-settings.json'
            save_cleanup_setting(legacy,False)
            migrate_cleanup_setting(new,legacy)
            self.assertFalse(load_cleanup_setting(new))
            self.assertFalse(legacy.exists())
            save_cleanup_setting(legacy,True)
            migrate_cleanup_setting(new,legacy)
            self.assertFalse(load_cleanup_setting(new))
            self.assertFalse(legacy.exists())

    def test_migration_failure_keeps_old_setting(self):
        from lumina_route_finder.session import migrate_cleanup_setting
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);legacy=root/'outputs/gui/gui-settings.json'
            save_cleanup_setting(legacy,False)
            with patch('lumina_route_finder.session.save_cleanup_setting',side_effect=OSError('read-only')):
                with self.assertRaises(OSError):migrate_cleanup_setting(root/'gui-settings.json',legacy)
            self.assertFalse(load_cleanup_setting(legacy))

    def test_default_output_parent_removed_only_when_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp)/'outputs';root=parent/'gui';root.mkdir(parents=True)
            session=SessionOutputs(root,parent_to_prune=parent)
            (parent/'notes.txt').write_text('keep',encoding='utf-8')
            self.assertEqual(session.cleanup(),[])
            self.assertFalse(root.exists())
            self.assertTrue((parent/'notes.txt').exists())
            (parent/'notes.txt').unlink()
            self.assertEqual(session.cleanup(),[])
            self.assertFalse(parent.exists())

    def test_default_enabled_and_setting_persists(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'gui-settings.json'
            self.assertTrue(load_cleanup_setting(path))
            save_cleanup_setting(path,False)
            self.assertFalse(load_cleanup_setting(path))
            save_cleanup_setting(path,True)
            self.assertTrue(load_cleanup_setting(path))
            path.write_text('broken',encoding='utf-8')
            self.assertTrue(load_cleanup_setting(path))

    def test_cleanup_only_removes_registered_generated_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=SessionOutputs(root)
            old=root/'old';old.mkdir();(old/'route.png').write_bytes(b'old')
            generated=root/'current';generated.mkdir();session.add_directory(generated)
            (generated/'route.png').write_bytes(b'generated')
            (generated/'result.json').write_text('{}',encoding='utf-8')
            (generated/'notes.txt').write_text('user notes',encoding='utf-8')
            clipboard=root/'clipboard';clipboard.mkdir()
            mine=clipboard/'new.png';mine.write_bytes(b'new');session.add_file(mine)
            previous=clipboard/'previous.png';previous.write_bytes(b'previous')
            settings=root/'gui-settings.json';save_cleanup_setting(settings,True)
            self.assertEqual(session.cleanup(),[])
            self.assertFalse((generated/'route.png').exists())
            self.assertTrue((generated/'notes.txt').exists())
            self.assertTrue((old/'route.png').exists())
            self.assertFalse(mine.exists())
            self.assertTrue(previous.exists())
            self.assertTrue(settings.exists())
            self.assertEqual(session.cleanup(),[])

    def test_clipboard_short_path_alias_is_registered_and_cleaned(self):
        import ctypes
        import os
        if os.name!='nt':self.skipTest('Windows short paths only')
        with tempfile.TemporaryDirectory() as temp:
            root=(Path(temp)/'Long output folder name').resolve()
            clipboard=root/'clipboard';clipboard.mkdir(parents=True)
            source=clipboard/'clipboard image.png';source.write_bytes(b'new')
            buffer=ctypes.create_unicode_buffer(32768)
            length=ctypes.windll.kernel32.GetShortPathNameW(str(source),buffer,len(buffer))
            if not length or length>=len(buffer):self.skipTest('Short path unavailable')
            alias=Path(buffer.value)
            if alias==source:self.skipTest('Filesystem does not provide a short alias')
            self.assertEqual(alias.resolve(),source)
            session=SessionOutputs(root)
            session.add_file(alias)
            self.assertEqual(session.cleanup(),[])
            self.assertFalse(source.exists())

    def test_empty_generated_directories_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);session=SessionOutputs(root)
            generated=root/'new';generated.mkdir();session.add_directory(generated)
            (generated/'input.png').write_bytes(b'input')
            self.assertEqual(session.cleanup(),[])
            self.assertFalse(generated.exists())
            self.assertFalse(root.exists())

    def test_outside_paths_and_root_cannot_be_registered(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'outputs';root.mkdir();session=SessionOutputs(root)
            outside=Path(temp)/'source.png';outside.write_bytes(b'original')
            for directory in [root,Path(temp)]:
                with self.assertRaises(ValueError):session.add_directory(directory)
            with self.assertRaises(ValueError):session.add_file(outside)
            self.assertEqual(outside.read_bytes(),b'original')

    def test_reparse_directory_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/'new';directory.mkdir()
            source=directory/'route.png';source.write_bytes(b'keep')
            session=SessionOutputs(root);session.add_directory(directory)
            with patch('lumina_route_finder.session.is_link',side_effect=lambda p:Path(p)==directory):
                self.assertIn(str(directory),session.cleanup())
            self.assertTrue(source.exists())


if __name__=='__main__':
    unittest.main()
