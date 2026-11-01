"""GUI configuration storage, validation and legacy migration."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from .file_safety import is_link


SEARCH_KEYS=('avoid_repeated','exclude_enabled','excluded_types','fallback_priority','objective','weights')

DEFAULT_SETTINGS={'delete_outputs_on_exit':True,'avoid_repeated':False,'exclude_enabled':False,
                  'excluded_types':[],'fallback_priority':'stage','initial_path_limit':20,'objective':'count','weights':{},'presets':{}}


def read_settings_document(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError,TypeError):
        return {}


def load_settings(path):
    from ..domain.catalog import CONTENT_NAMES
    raw=read_settings_document(path)
    result=dict(DEFAULT_SETTINGS,excluded_types=[])
    for key in ('delete_outputs_on_exit','avoid_repeated','exclude_enabled'):
        if isinstance(raw.get(key),bool):result[key]=raw[key]
    if raw.get('fallback_priority') in ('stage','count','none'):
        result['fallback_priority']=raw['fallback_priority']
    limit=raw.get('initial_path_limit')
    if type(limit) is int and 1<=limit<=1000:result['initial_path_limit']=limit
    if isinstance(raw.get('excluded_types'),list):
        result['excluded_types']=[key for key in CONTENT_NAMES if key in raw['excluded_types']]
    if raw.get('objective') in ('count','weight','count_then_weight'):result['objective']=raw['objective']
    result['weights']={k:v for k,v in raw.get('weights',{}).items() if k in CONTENT_NAMES and type(v) in (int,float) and math.isfinite(v) and abs(v)<=1000000} if isinstance(raw.get('weights'),dict) else {}
    result['presets']={}
    if isinstance(raw.get('presets'),dict):
        for name,values in raw['presets'].items():
            if isinstance(name,str) and name.strip() and len(name)<=80 and isinstance(values,dict):
                result['presets'][name]={k:v for k,v in values.items() if k in SEARCH_KEYS}
    return result


def save_settings(path,values):
    # Keep unknown keys so a checkbox change cannot erase future extensions.
    document=read_settings_document(path)
    document.update(values)
    _write_settings(path,document)


def default_settings_path():
    base=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]
    return base/'gui-settings.json'


def read_cleanup_setting(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8-sig'))['delete_outputs_on_exit']
        return value if isinstance(value,bool) else None
    except (OSError,ValueError,KeyError,TypeError):
        return None


def load_cleanup_setting(path):
    value=read_cleanup_setting(path)
    return True if value is None else value


def migrate_cleanup_setting(path,legacy):
    path,legacy=Path(path),Path(legacy)
    if path.absolute()==legacy.absolute() or is_link(legacy) or is_link(path):
        return
    previous=read_cleanup_setting(legacy)
    if previous is None:
        return
    if read_cleanup_setting(path) is None:
        save_settings(path,dict(read_settings_document(legacy),**load_settings(legacy)))
    # Only remove a valid old settings file once the new file is readable.
    if read_cleanup_setting(path) is not None:
        legacy.unlink()


def save_cleanup_setting(path, enabled):
    save_settings(path,{'delete_outputs_on_exit':bool(enabled)})


def _write_settings(path,document):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.gui-settings-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(document,stream,indent=2)
            stream.write('\n')
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)




def normalize_search(values):
    from ..domain.catalog import CONTENT_NAMES
    result={k:DEFAULT_SETTINGS[k] for k in SEARCH_KEYS}
    for key in ('avoid_repeated','exclude_enabled'):
        if isinstance(values.get(key),bool):result[key]=values[key]
    if values.get('fallback_priority') in ('stage','count','none'):result['fallback_priority']=values['fallback_priority']
    if values.get('objective') in ('count','weight','count_then_weight'):result['objective']=values['objective']
    raw=values.get('excluded_types',[])
    result['excluded_types']=[k for k in CONTENT_NAMES if k in raw] if isinstance(raw,list) else []
    raw=values.get('weights',{})
    result['weights']={k:v for k,v in raw.items() if k in CONTENT_NAMES and type(v) in (int,float) and math.isfinite(v) and abs(v)<=1000000} if isinstance(raw,dict) else {}
    return result
