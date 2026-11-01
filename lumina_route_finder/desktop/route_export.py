"""Persist and copy the selected route, independently of session cleanup."""
import io
import sys
from pathlib import Path
import cv2
from PIL import Image
from ..storage.images import write_image
from ..rendering.routes import render_route


def candidate_image(board,result,page=0,selected=None):
    if result is None or result.get('status') not in ('ok','partial'):raise ValueError('表示できる候補がありません。')
    return render_route(board,[(r-1,c-1) for r,c in result['paths'][page]],selected=selected)


def save_candidate(path,board,result,page,output_root,selected=None):
    path=Path(path).resolve()
    if path.is_relative_to(Path(output_root).resolve()):raise ValueError('終了時削除の対象外へ保存するため、解析出力フォルダー以外を選んでください。')
    write_image(path,candidate_image(board,result,page,selected))


def dib_bytes(image):
    stream=io.BytesIO();Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB)).convert('RGB').save(stream,format='BMP')
    return stream.getvalue()[14:]


def copy_image(image,owner):
    if sys.platform!='win32':raise RuntimeError('画像コピーはWindows版で利用できます。PNG保存をご利用ください。')
    import ctypes as c
    from ctypes import wintypes as w
    data=dib_bytes(image);kernel=c.WinDLL('kernel32',use_last_error=True);user=c.WinDLL('user32',use_last_error=True)
    kernel.GlobalAlloc.argtypes=[w.UINT,c.c_size_t];kernel.GlobalAlloc.restype=c.c_void_p
    kernel.GlobalLock.argtypes=[c.c_void_p];kernel.GlobalLock.restype=c.c_void_p
    kernel.GlobalUnlock.argtypes=[c.c_void_p];kernel.GlobalFree.argtypes=[c.c_void_p]
    user.OpenClipboard.argtypes=[w.HWND];user.OpenClipboard.restype=w.BOOL
    user.SetClipboardData.argtypes=[w.UINT,c.c_void_p];user.SetClipboardData.restype=c.c_void_p
    handle=kernel.GlobalAlloc(2,len(data))
    if not handle:raise c.WinError(c.get_last_error())
    opened=False
    try:
        pointer=kernel.GlobalLock(handle)
        if not pointer:raise c.WinError(c.get_last_error())
        c.memmove(pointer,data,len(data));kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(owner):raise OSError('クリップボードが使用中です。少し待ってから再試行してください。')
        opened=True
        if not user.EmptyClipboard() or not user.SetClipboardData(8,handle):raise c.WinError(c.get_last_error())
        handle=None  # Ownership transferred to the operating system.
    finally:
        if opened:user.CloseClipboard()
        if handle:kernel.GlobalFree(handle)
