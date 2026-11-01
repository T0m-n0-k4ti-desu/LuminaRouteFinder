"""Create a portable ZIP containing only the executable and default settings."""
import json
import os
from pathlib import Path
import tempfile
import zipfile


def create_portable_zip(executable,settings_template,archive):
    executable,settings_template,archive=map(Path,(executable,settings_template,archive))
    config=json.loads(settings_template.read_text(encoding='utf-8-sig'))
    if not isinstance(config.get('delete_outputs_on_exit'),bool):
        raise ValueError('Default settings must specify a boolean cleanup preference')
    archive.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.portable-',suffix='.zip',dir=archive.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(executable,'LuminaRouteFinder.exe')
            bundle.writestr('gui-settings.json',json.dumps(config,indent=2)+'\n')
        os.replace(name,archive)
    finally:
        Path(name).unlink(missing_ok=True)
    return archive
