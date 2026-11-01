"""Pure Japanese result formatting, independent of Tk and image matching."""
from ..domain.catalog import CONTENT_NAMES

ERROR_MESSAGES = {
    'AMBIGUOUS_CONTENT': 'コンテンツの種類を確定できません。画像の画質や遮蔽を確認するか、除外オプションをオフにしてください。',
    'INVALID_REGION': '解析範囲が小さすぎるか、画像の外にはみ出しています。全50アイコンと接続線を含む範囲を指定してください。',
    'INPUT_READ_ERROR': '画像を読み込めません。ファイルが存在し、対応する画像形式か確認してください。',
    'BOARD_NOT_FOUND': '盤面を検出できません。5列・全10段階のアイコンと接続線が残る画像を指定してください。強く縮小された画像は元の画質で撮影し直してください。',
    'MULTIPLE_BOARDS': '盤面ウィンドウが複数あります。対象を1つにして撮影してください。',
    'UNSUPPORTED_LAYOUT': 'この画面配置・倍率には対応していません。強い縦横の変形を避け、十分な大きさで撮影してください。',
    'INCOMPLETE_BOARD': '下の段のアイコンが選択され、上側の経路が非表示です。選択を解除し、全経路が見える状態で撮影してください。',
    'CURSOR_OCCLUSION': 'ゲーム内カーソルが盤面に重なっています。カーソルを盤面外に移動して撮影してください。',
    'AMBIGUOUS_CONNECTION': '接続線を確定できません。遮蔽や画像の劣化を確認し、撮影し直してください。',
    'INVALID_BOARD_STRUCTURE': 'アイコンの配置・輪郭を確認できません。盤面全体が遮られずに写っているか確認してください。',
}


def describe_result(result, page=0):
    """Return a user-facing title, details and whether this is a success."""
    if result['status'] in ('ok','partial'):
        count = result['max_count']
        total = result['optimal_path_count']
        path = result['paths'][page]
        details = f'同率の最長経路: {total}通り\n候補 {page+1}/{len(result["paths"])} を表示しています。\n\n通過順（段階・列）\n'
        kinds = result.get('content_types')
        details += '\n'.join(f'{i:2}. 第{r}段階・{c}列目' +
                             ('（'+CONTENT_NAMES[kinds[r-1][c-1]]+'）'
                              if kinds and kinds[r-1][c-1] in CONTENT_NAMES else '')
                             for i, (r,c) in enumerate(path,1))
        details = describe_filters(result) + details
        if result['status']=='partial':
            stage=result['reached_stage']
            priority='到達段階を優先' if result.get('fallback_priority')=='stage' else '通過アイコン数を優先'
            details=f'ゴール未到達 · 第{stage}段階まで\n{priority}で途中経路を表示しています。\n\n'+details
            return f'ゴール未到達 · 第{stage}段階・{count}アイコン',details,True
        return f'解析完了 · 最大{count}アイコン', details, True
    if result['status'] == 'no_path':
        return 'ゴールに到達できません', describe_filters(result)+'現在の接続と探索条件では第1段階から第10段階への経路がありません。条件を緩めるか、接続確認画像 recognized.png を確認してください。', False
    messages = []
    for error in result.get('errors', []):
        code = error['code']
        message = ERROR_MESSAGES.get(code, error.get('message', '不明なエラーです。'))
        text = f'{message}\n[{code}]'
        if text not in messages:
            messages.append(text)
    return '解析できませんでした', '\n\n'.join(messages), False

def describe_filters(result):
    filters = result.get('filters', {})
    lines = []
    if filters.get('avoid_repeated'):
        lines.append('同じコンテンツの連続を禁止')
    if filters.get('excluded_types'):
        lines.append('除外: '+ '、'.join(CONTENT_NAMES[k] for k in filters['excluded_types']))
    return '\n'.join(lines)+'\n\n' if lines else ''
