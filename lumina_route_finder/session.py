"""Settings and bounded cleanup of files created by one GUI process."""
from pathlib import Path
import threading

from .file_safety import is_link
# Backwards-compatible public imports; configuration itself lives in settings.py.
from .settings import (DEFAULT_SETTINGS, read_settings_document, load_settings,
                       save_settings, default_settings_path, read_cleanup_setting,
                       load_cleanup_setting, migrate_cleanup_setting, save_cleanup_setting)

ARTIFACTS={'result.json','board.json','board.png','route.png','recognized.png','error.png','input.png'}




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
