"""Shared error contract across recognition, application boundaries and presentation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lumina_route_finder.errors import ApplicationError, RecognitionError, ErrorCode, issue, failure_issues, error_result
from lumina_route_finder.error_messages import error_message, format_issues
from lumina_route_finder.ui.presentation import describe_result
from lumina_route_finder.cli import main


class ErrorTests(unittest.TestCase):
    def test_enum_codes_keep_existing_json_schema_and_recognition_subtype(self):
        error=RecognitionError([issue(ErrorCode.INVALID_REGION,'invalid bounds',(1.2,2,3,4))],origin=(10,20))
        self.assertIsInstance(error,ApplicationError)
        self.assertEqual(json.loads(json.dumps(error_result(error))),{
            'status':'error','errors':[{'code':'INVALID_REGION','message':'invalid bounds','board_box':[1,2,3,4]}]})
        self.assertEqual(str(error),'INVALID_REGION')
        self.assertEqual(error.origin,(10,20))

    def test_boundary_keeps_expected_failure_and_distinguishes_io_from_internal(self):
        expected=ApplicationError([issue(ErrorCode.INVALID_CONTENT_TYPE,'unknown kind')])
        self.assertIs(failure_issues(expected),expected.issues)
        for failure,code in [(PermissionError('read-only'),ErrorCode.OUTPUT_WRITE_ERROR),
                             (RuntimeError('worker failed'),ErrorCode.ANALYSIS_FAILED)]:
            normalized=error_result(failure)
            self.assertEqual(normalized['errors'][0]['code'],code)
            self.assertEqual(normalized['errors'][0]['message'],str(failure))

    def test_shared_messages_preserve_diagnostics_unknown_codes_and_deduplicate(self):
        known=issue(ErrorCode.BOARD_NOT_FOUND,'header missing')
        title,details,success=describe_result({'status':'error','errors':[known,known]})
        self.assertFalse(success)
        self.assertEqual(details.count('[BOARD_NOT_FOUND]'),1)
        self.assertIn('盤面を検出できません',details)
        self.assertIn('header missing',format_issues([known],include_detail=True))
        self.assertEqual(format_issues([issue('FUTURE_CODE','new diagnostic')],include_code=True),
                         'new diagnostic\n[FUTURE_CODE]')
        self.assertIn('sudo apt install',error_message(ErrorCode.CLIPBOARD_UNAVAILABLE))

    def test_cli_reports_output_error_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.jpg';source.write_bytes(b'input')
            output=io.StringIO()
            with patch('lumina_route_finder.cli.run_image',side_effect=PermissionError('read-only')), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                code=main([str(source),'--output-dir',str(Path(temp)/'output')])
            self.assertEqual(code,1)
            self.assertIn('OUTPUT_WRITE_ERROR',output.getvalue())

    def test_cli_reports_unexpected_failure_with_distinct_code_and_detail(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.jpg';source.write_bytes(b'input')
            output,diagnostic=io.StringIO(),io.StringIO()
            with patch('lumina_route_finder.cli.run_image',side_effect=RuntimeError('worker failed')), contextlib.redirect_stdout(output), contextlib.redirect_stderr(diagnostic):
                code=main([str(source),'--output-dir',str(Path(temp)/'output')])
        self.assertEqual(code,1)
        self.assertIn('ANALYSIS_FAILED',output.getvalue())
        self.assertIn('worker failed',diagnostic.getvalue())
        self.assertIn('解析処理を完了できませんでした',diagnostic.getvalue())

    def test_invalid_exclusion_uses_the_shared_error_result(self):
        from lumina_route_finder.analysis import run_image
        source=Path(__file__).resolve().parents[1]/'docs/images/sample_image.jpg'
        with tempfile.TemporaryDirectory() as temp:
            result=run_image(source,Path(temp),excluded_types=['unknown_content'])
            serialized=json.loads((Path(temp)/'result.json').read_text())
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['errors'][0]['code'],'INVALID_CONTENT_TYPE')
        self.assertEqual(result,serialized)
        self.assertNotIn('max_count',result)


if __name__=='__main__':
    unittest.main()
