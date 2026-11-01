"""Pure Japanese result formatting, independent of Tk and image matching."""
from ..domain.catalog import CONTENT_NAMES
from ..shared.messages import ERROR_MESSAGES, format_issues



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
        mode=result.get('objective','count')
        mode_text={'count':'通過数最大','weight':'重み合計最大','count_then_weight':'通過数優先・同数時に重み'}[mode]
        if mode!='count':details=f'評価: {mode_text} / 重み合計 {result["path_weights"][page]:g}\n\n'+details
        details = describe_filters(result) + details
        if result['status']=='partial':
            stage=result['reached_stage']
            priority='到達段階を優先' if result.get('fallback_priority')=='stage' else ('通過アイコン数を優先' if mode=='count' else '設定した経路評価を優先')
            details=f'ゴール未到達 · 第{stage}段階まで\n{priority}で途中経路を表示しています。\n\n'+details
            return f'ゴール未到達 · 第{stage}段階・{count}アイコン',details,True
        if mode!='count':return f'解析完了 · {mode_text}・{count}アイコン',details,True
        return f'解析完了 · 最大{count}アイコン', details, True
    if result['status'] == 'no_path':
        return 'ゴールに到達できません', describe_filters(result)+'現在の接続と探索条件では第1段階から第10段階への経路がありません。条件を緩めるか、接続確認画像 recognized.png を確認してください。', False
    return '解析できませんでした', format_issues(result.get('errors', []), include_code=True), False

def describe_filters(result):
    filters = result.get('filters', {})
    lines = []
    if filters.get('avoid_repeated'):
        lines.append('同じコンテンツの連続を禁止')
    if filters.get('excluded_types'):
        lines.append('除外: '+ '、'.join(CONTENT_NAMES[k] for k in filters['excluded_types']))
    return '\n'.join(lines)+'\n\n' if lines else ''
