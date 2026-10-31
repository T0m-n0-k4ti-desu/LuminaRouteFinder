"""Double-click launcher for Windows (run with pythonw)."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
try:
    from lumina_route_finder.gui import main
except ImportError as exc:
    from tkinter import messagebox
    messagebox.showerror('LuminaRouteFinder を起動できません',
        '必要なライブラリが見つかりません。\nリポジトリ内で次を実行してください。\n\n'
        'python -m pip install -r requirements.txt\n\n' + str(exc))
else:
    main()
