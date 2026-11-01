import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec=importlib.util.spec_from_file_location('publish_release',Path(__file__).resolve().parents[1]/'tools/release/publish.py')
release=importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.folder=Path(self.tmp.name).resolve()
        exe=self.folder/release.ASSETS[0];exe.write_bytes(b'MZ-release-example')
        archive=self.folder/release.ASSETS[1]
        with zipfile.ZipFile(archive,'w') as bundle:
            bundle.write(exe,exe.name)
            bundle.writestr('gui-settings.json',json.dumps({'delete_outputs_on_exit':True}))
        (self.folder/release.ASSETS[2]).write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in (exe,archive)),encoding='ascii')
        self.assets=[{'name':name,'digest':'sha256:'+hashlib.sha256((self.folder/name).read_bytes()).hexdigest()} for name in release.ASSETS]
        self.draft={'tag_name':'v9.9.9','draft':True,'id':123}

    def tearDown(self):
        self.tmp.cleanup()

    def test_cli_decodes_japanese_json_with_non_utf8_system_locale(self):
        import sys
        payload={'body':'日本語のリリース情報'}
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        child="import sys; sys.stdout.buffer.write(bytes.fromhex("+repr(data.hex())+"))"
        run=subprocess.run
        def run_child(args,**kwargs):
            return run([sys.executable,'-c',child],**kwargs)
        with patch.object(release.subprocess,'run',side_effect=run_child),patch('subprocess._text_encoding',return_value='cp1252',create=True):
            self.assertEqual(release.gh(['api','releases'],True),payload)

    def test_dry_run_verifies_all_three_without_network(self):
        with patch.object(release,'gh') as gh:
            result=release.publish('v9.9.9','owner/repo',self.folder,True)
            gh.assert_not_called()
        self.assertEqual(result['assets'],list(release.ASSETS))

    def test_upload_contains_zip_and_publish_happens_last(self):
        with patch.object(release,'gh',side_effect=[[], '', [self.draft], [], '', self.assets, '']) as gh:
            release.publish('v9.9.9','owner/repo',self.folder)
        commands=[call.args[0] for call in gh.call_args_list]
        upload=next(c for c in commands if c[:2]==['release','upload'])
        for name in release.ASSETS:self.assertIn(str(self.folder/name),upload)
        self.assertNotIn('--clobber',upload)
        self.assertEqual(commands[-1][:2],['release','edit'])
        self.assertIn('--draft=false',commands[-1])
        self.assertIn('--draft',commands[1])
        self.assertIn('--verify-tag',commands[1])

    def test_delayed_draft_and_asset_listing_is_retried_before_publishing(self):
        responses=[[], '', [], [self.draft], [], '', [], self.assets, '']
        with patch.object(release.time,'sleep'),patch.object(release,'gh',side_effect=responses) as gh:
            release.publish('v9.9.9','owner/repo',self.folder)
        self.assertEqual(gh.call_args_list[-1].args[0][:2],['release','edit'])

    def test_upload_failure_leaves_release_unpublished(self):
        failure=subprocess.CalledProcessError(1,['gh','release','upload'])
        with patch.object(release,'gh',side_effect=[[], '', [self.draft], [], failure]) as gh:
            with self.assertRaises(subprocess.CalledProcessError):
                release.publish('v9.9.9','owner/repo',self.folder)
        self.assertFalse(any(c.args[0][:2]==['release','edit'] for c in gh.call_args_list))

    def test_missing_zip_on_server_prevents_publishing(self):
        with patch.object(release.time,'sleep'),patch.object(release,'gh',side_effect=[[self.draft], [], '']+[[self.assets[0],self.assets[2]]]*10) as gh:
            with self.assertRaisesRegex(ValueError,'could not be verified'):
                release.publish('v9.9.9','owner/repo',self.folder)
        self.assertFalse(any(c.args[0][:2]==['release','edit'] for c in gh.call_args_list))

    def test_public_release_and_differing_draft_asset_are_not_overwritten(self):
        for responses in [[[dict(self.draft,draft=False)]],[[self.draft],[{'name':release.ASSETS[0],'digest':'sha256:different'}]]]:
            with patch.object(release,'gh',side_effect=responses) as gh:
                with self.assertRaises(ValueError):release.publish('v9.9.9','owner/repo',self.folder)
            self.assertFalse(any(c.args[0][:2] in [['release','upload'],['release','edit']] for c in gh.call_args_list))

    def test_resume_matching_draft_only_uploads_missing_assets(self):
        with patch.object(release,'gh',side_effect=[[self.draft],[self.assets[0]],'',self.assets,'']) as gh:
            release.publish('v9.9.9','owner/repo',self.folder)
        commands=[c.args[0] for c in gh.call_args_list]
        upload=next(c for c in commands if c[:2]==['release','upload'])
        self.assertNotIn(str(self.folder/release.ASSETS[0]),upload)
        self.assertIn(str(self.folder/release.ASSETS[1]),upload)

    def test_bad_checksum_or_missing_file_prevents_network_access(self):
        (self.folder/release.ASSETS[0]).write_bytes(b'changed')
        with patch.object(release,'gh') as gh:
            with self.assertRaisesRegex(ValueError,'Checksum mismatch'):
                release.publish('v9.9.9','owner/repo',self.folder)
            gh.assert_not_called()
        (self.folder/release.ASSETS[1]).unlink()
        with self.assertRaisesRegex(ValueError,'Missing release asset'):release.verify_assets(self.folder)

    def test_tag_must_be_stable_version(self):
        with patch.object(release,'gh') as gh:
            with self.assertRaises(ValueError):release.publish('--bad','owner/repo',self.folder)
            gh.assert_not_called()


if __name__=='__main__':
    unittest.main()
