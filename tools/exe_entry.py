"""Entry point for the standalone Windows application."""
import os
from pathlib import Path
import sys

from lumina_route_finder.gui import main

base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
os.chdir(base)

if '--smoke-test' in sys.argv:
    import argparse
    import json
    from tkinterdnd2 import TkinterDnD
    from lumina_route_finder.gui import Application
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke-test',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    root=TkinterDnD.Tk()
    root.withdraw()
    app=Application(root,args.report.parent/'analysis')
    app.path.set(str(args.smoke_test))
    app.start()
    exit_code=[1]
    def finish():
        if app.busy:
            root.after(100,finish)
            return
        result={'title':app.status.cget('text'),'has_preview':app.image is not None,
                'status': app.result.get('status') if app.result else 'failed',
                'max_count':app.result.get('max_count') if app.result else None,
                'tkdnd':root.tk.call('package','present','tkdnd')}
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        exit_code[0]=0 if result['status']=='ok' and result['has_preview'] else 1
        app.close()
    root.after(100,finish)
    root.after(30000,lambda:app.close() if not app.closed else None)
    root.mainloop()
    sys.exit(exit_code[0])
else:
    main()
