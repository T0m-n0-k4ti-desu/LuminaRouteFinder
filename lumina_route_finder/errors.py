"""Shared, UI-independent error codes and structured application failures.

Developer-facing diagnostics stay in message; localization belongs to
error_messages.py. Wire codes remain strings for existing JSON consumers.
"""
from enum import Enum


class ErrorCode(str, Enum):
    AMBIGUOUS_CONTENT = 'AMBIGUOUS_CONTENT'
    INVALID_REGION = 'INVALID_REGION'
    INPUT_READ_ERROR = 'INPUT_READ_ERROR'
    BOARD_NOT_FOUND = 'BOARD_NOT_FOUND'
    MULTIPLE_BOARDS = 'MULTIPLE_BOARDS'
    UNSUPPORTED_LAYOUT = 'UNSUPPORTED_LAYOUT'
    INCOMPLETE_BOARD = 'INCOMPLETE_BOARD'
    CURSOR_OCCLUSION = 'CURSOR_OCCLUSION'
    AMBIGUOUS_CONNECTION = 'AMBIGUOUS_CONNECTION'
    INVALID_BOARD_STRUCTURE = 'INVALID_BOARD_STRUCTURE'
    INPUT_NOT_FOUND = 'INPUT_NOT_FOUND'
    INVALID_FILE_COUNT = 'INVALID_FILE_COUNT'
    MISSING_EXCLUSION_TARGET = 'MISSING_EXCLUSION_TARGET'
    INVALID_CONTENT_TYPE = 'INVALID_CONTENT_TYPE'
    CLIPBOARD_EMPTY = 'CLIPBOARD_EMPTY'
    CLIPBOARD_UNAVAILABLE = 'CLIPBOARD_UNAVAILABLE'
    CLIPBOARD_READ_ERROR = 'CLIPBOARD_READ_ERROR'
    ANALYSIS_FAILED = 'ANALYSIS_FAILED'
    OUTPUT_WRITE_ERROR = 'OUTPUT_WRITE_ERROR'
    OUTPUT_OPEN_ERROR = 'OUTPUT_OPEN_ERROR'
    SETTINGS_SAVE_ERROR = 'SETTINGS_SAVE_ERROR'
    SETTINGS_MIGRATION_ERROR = 'SETTINGS_MIGRATION_ERROR'
    REGION_TOO_SMALL = 'REGION_TOO_SMALL'
    OUTPUT_CLEANUP_ERROR = 'OUTPUT_CLEANUP_ERROR'


class ApplicationError(Exception):
    """Expected failure that can be reported by any application entry point."""
    def __init__(self, issues, board=None, origin=None):
        self.issues, self.board, self.origin = issues, board, origin
        super().__init__('; '.join(i['code'] for i in issues))


class RecognitionError(ApplicationError):
    """Compatibility subtype for image/board recognition failures."""


def issue(code, message, box=None):
    item = {'code': code.value if isinstance(code, ErrorCode) else code, 'message': message}
    if box is not None:
        item['board_box'] = list(map(int, box))
    return item


def failure_issues(exc):
    """Normalize failures at CLI/worker boundaries without losing expected codes."""
    if isinstance(exc, ApplicationError):
        return exc.issues
    code = ErrorCode.OUTPUT_WRITE_ERROR if isinstance(exc, OSError) else ErrorCode.ANALYSIS_FAILED
    return [issue(code, str(exc))]


def error_result(exc):
    return {'status': 'error', 'errors': failure_issues(exc)}
