"""Filesystem-link checks shared by settings migration and session cleanup."""
import stat

def is_link(path):
    try:
        info=path.lstat()
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
    except FileNotFoundError:
        return False
