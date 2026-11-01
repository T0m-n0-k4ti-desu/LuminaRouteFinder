"""Settings and bounded cleanup of files created by one GUI process."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading

ARTIFACTS={'result.json','board.json','board.png','route.png','recognized.png','error.png','input.png'}


def default_settings_path():
    base=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
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
        save_cleanup_setting(path,previous)
    # Only remove a valid old settings file once the new file is readable.
    if read_cleanup_setting(path) is not None:
        legacy.unlink()


def save_cleanup_setting(path, enabled):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.gui-settings-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump({'delete_outputs_on_exit':bool(enabled)},stream,indent=2)
            stream.write('\n')
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)


def is_link(path):
    try:
        info=path.lstat()
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
    except FileNotFoundError:
        return False


class SessionOutputs:
    """Never discover or recursively delete old, external or unregistered data."""
    def __init__(self, root, parent_to_prune=None):
        self.root=Path(root).resolve()
        self.parent_to_prune=Path(parent_to_prune).resolve() if parent_to_prune is not None else None
        if self.parent_to_prune is not None and self.root.parent!=self.parent_to_prune:
            raise ValueError('Only the immediate output parent can be pruned')
        self.directories=set()
        self.files=set()
        self.lock=threading.Lock()

    def add_directory(self,path):
        path=Path(path).absolute()
        if path.parent.resolve()!=self.root or path.resolve().parent!=self.root or is_link(path):
            raise ValueError('Generated directory must be directly inside the output folder')
        with self.lock:
            self.directories.add(path)

    def add_file(self,path):
        path=Path(path).absolute()
        if path.parent.resolve()!=self.root/'clipboard' or path.resolve().parent!=self.root/'clipboard' or is_link(path):
            raise ValueError('Generated clipboard file must be inside the clipboard folder')
        with self.lock:
            self.files.add(path)

    def prune_empty(self):
        failures=[]
        paths=[self.root]
        if self.parent_to_prune is not None:
            paths.append(self.parent_to_prune)
        for path in paths:
            if path.parent==path or is_link(path) or path.resolve()!=path:
                continue
            try:
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            except OSError:
                failures.append(str(path))
        return failures

    def cleanup(self):
        """Return failures; leave user-added files and previous sessions intact."""
        failures=[]
        if self.root.resolve()!=self.root or is_link(self.root):
            return [str(self.root)]
        with self.lock:
            directories=list(self.directories)
            files=list(self.files)
        for directory in directories:
            if not directory.exists() and not is_link(directory):
                continue
            if is_link(directory) or directory.resolve().parent!=self.root:
                failures.append(str(directory));continue
            for name in ARTIFACTS:
                path=directory/name
                try:
                    if is_link(path):
                        failures.append(str(path));continue
                    path.unlink(missing_ok=True)
                except OSError:
                    failures.append(str(path))
            try:
                # Non-empty directories (e.g. user-added notes) are preserved.
                if not any(directory.iterdir()):
                    directory.rmdir()
            except OSError:
                failures.append(str(directory))
        for path in files:
            try:
                if is_link(path.parent) or path.parent.resolve()!=self.root/'clipboard' or is_link(path):
                    failures.append(str(path));continue
                path.unlink(missing_ok=True)
            except OSError:
                failures.append(str(path))
        clipboard=self.root/'clipboard'
        try:
            if clipboard.is_dir() and not is_link(clipboard) and not any(clipboard.iterdir()):
                clipboard.rmdir()
        except OSError:
            pass
        failures.extend(self.prune_empty())
        return failures
