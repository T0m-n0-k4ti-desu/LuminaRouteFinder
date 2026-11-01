"""Shared Japanese error presentation, with no dependency on GUI or images."""
from .errors import ErrorCode, issue

ERROR_MESSAGES = {
    ErrorCode.AMBIGUOUS_CONTENT: 'コンテンツの種類を確定できません。画像の画質や遮蔽を確認するか、除外オプションをオフにしてください。',
    ErrorCode.INVALID_REGION: '解析範囲が小さすぎるか、画像の外にはみ出しています。全50アイコンと接続線を含む範囲を指定してください。',
    ErrorCode.INPUT_READ_ERROR: '画像を読み込めません。ファイルが存在し、対応する画像形式か確認してください。',
    ErrorCode.BOARD_NOT_FOUND: '盤面を検出できません。5列・全10段階のアイコンと接続線が残る画像を指定してください。強く縮小された画像は元の画質で撮影し直してください。',
    ErrorCode.MULTIPLE_BOARDS: '盤面ウィンドウが複数あります。対象を1つにして撮影してください。',
    ErrorCode.UNSUPPORTED_LAYOUT: 'この画面配置・倍率には対応していません。強い縦横の変形を避け、十分な大きさで撮影してください。',
    ErrorCode.INCOMPLETE_BOARD: '下の段のアイコンが選択され、上側の経路が非表示です。選択を解除し、全経路が見える状態で撮影してください。',
    ErrorCode.CURSOR_OCCLUSION: 'ゲーム内カーソルが盤面に重なっています。カーソルを盤面外に移動して撮影してください。',
    ErrorCode.AMBIGUOUS_CONNECTION: '接続線を確定できません。遮蔽や画像の劣化を確認し、撮影し直してください。',
    ErrorCode.INVALID_BOARD_STRUCTURE: 'アイコンの配置・輪郭を確認できません。盤面全体が遮られずに写っているか確認してください。',
    ErrorCode.INPUT_NOT_FOUND: '存在する画像ファイルを指定してください。フォルダーは指定できません。',
    ErrorCode.INVALID_FILE_COUNT: '画像を1枚だけドロップしてください。',
    ErrorCode.MISSING_EXCLUSION_TARGET: '除外するコンテンツを1つ以上選択するか、「指定コンテンツを除外」のチェックを外してください。',
    ErrorCode.INVALID_CONTENT_TYPE: '除外対象に不明なコンテンツの種類が指定されています。',
    ErrorCode.CLIPBOARD_EMPTY: 'クリップボードに画像がありません。Win＋Shift＋Sで対象ウィンドウをコピーしてから貼り付けてください。',
    ErrorCode.CLIPBOARD_UNAVAILABLE: 'この環境ではクリップボード画像を取得できません。Linux / WSLでは、\nsudo apt install wl-clipboard xclip\nで必要なツールを導入してください。画像をファイルに保存し、参照から開くこともできます。',
    ErrorCode.CLIPBOARD_READ_ERROR: 'クリップボード画像を読み込めませんでした。コピーし直してください。',
    ErrorCode.ANALYSIS_FAILED: '解析処理を完了できませんでした。',
    ErrorCode.OUTPUT_WRITE_ERROR: '解析結果を保存できませんでした。保存先と書き込み権限を確認してください。',
    ErrorCode.OUTPUT_OPEN_ERROR: 'フォルダーを開けませんでした。',
    ErrorCode.SETTINGS_SAVE_ERROR: '設定を保存できませんでした。今回の選択は有効ですが、次回起動時には引き継がれません。',
    ErrorCode.SETTINGS_MIGRATION_ERROR: '旧設定を移行できませんでした。保存先の権限を確認してください。',
    ErrorCode.REGION_TOO_SMALL: '指定範囲が小さすぎます。全50個のアイコンと接続線を含むように囲んでください。',
    ErrorCode.OUTPUT_CLEANUP_ERROR: '使用中のファイルや安全に削除できないファイルは残しました。',
}


def format_issue(error, *, include_code=False, include_detail=False):
    code = error['code']
    if isinstance(code, ErrorCode):
        code = code.value
    diagnostic = error.get('message', '')
    message = ERROR_MESSAGES.get(code, diagnostic or '不明なエラーです。')
    if include_detail and diagnostic and diagnostic != message and code in ERROR_MESSAGES:
        message += '\n\n' + diagnostic
    return message + (f'\n[{code}]' if include_code else '')


def format_issues(errors, *, include_code=False, include_detail=False):
    messages = [format_issue(error, include_code=include_code, include_detail=include_detail) for error in errors]
    return '\n\n'.join(dict.fromkeys(messages))


def error_message(code, detail=None):
    return format_issue(issue(code, detail or ''), include_detail=detail is not None)
