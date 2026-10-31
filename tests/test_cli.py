import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from lumina_route_finder.__main__ import main


class CliTests(unittest.TestCase):
    def test_graph_json_coordinates_and_output(self):
        with tempfile.TemporaryDirectory(prefix='lumina_') as tmp:
            root=Path(tmp)
            source=root/'盤面.json'
            source.write_text(json.dumps({'nodes':[[1,1],[1,2],[2,2]],
                'edges':[{'from':[1,1],'to':[1,2]},{'from':[1,2],'to':[2,2]}]}),encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                code=main([str(source),'--graph','--output-dir',str(root/'result')])
            result=json.loads((root/'result/result.json').read_text(encoding='utf-8'))
            self.assertEqual(code,0)
            self.assertEqual(result['max_count'],3)
            self.assertEqual(result['paths'][0],[[1,1],[1,2],[2,2]])

    def test_corrupt_input_outputs_error_and_preserves_earlier_runs(self):
        with tempfile.TemporaryDirectory(prefix='lumina_') as tmp:
            root=Path(tmp)
            source=root/'画像.jpg'
            source.write_bytes(b'invalid image')
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(2):
                    self.assertEqual(main([str(source),'--output-dir',str(root/'out')]),1)
            for folder in ['画像.jpg','画像.jpg.1']:
                result=json.loads((root/'out'/folder/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(result['status'],'error')
                self.assertEqual(result['errors'][0]['code'],'INPUT_READ_ERROR')
                self.assertNotIn('max_count',result)

    def test_invalid_graph_rejected(self):
        with tempfile.TemporaryDirectory(prefix='lumina_') as tmp:
            source=Path(tmp)/'board.json'
            source.write_text('{',encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main([str(source),'--graph'])
            self.assertEqual(caught.exception.code,2)


if __name__=='__main__':
    unittest.main()
