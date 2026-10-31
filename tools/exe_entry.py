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
    parser.add_argument('--clipboard-test',action='store_true')
    parser.add_argument('--region-test',action='store_true')
    parser.add_argument('--scaled-header-test',action='store_true')
    args=parser.parse_args()
    root=TkinterDnD.Tk()
    root.withdraw()
    app=Application(root,args.report.parent/'analysis')
    app.delete_outputs.set(True)
    if args.clipboard_test:
        from PIL import Image
        with Image.open(args.smoke_test) as source:
            app.load_pasted_image(source)
    else:
        app.path.set(str(args.smoke_test))
    if args.region_test:
        app.region=(715,327,975,827)
    if args.scaled_header_test:
        # Exercise the PR fallback in a separate diagnostic process, including
        # the GUI worker and packaged assets, even if this image has a good grid.
        import lumina_route_finder.locate as locator
        locator.find_grids=lambda image: []
    app.start()
    exit_code=[1]
    def finish():
        if app.busy:
            root.after(100,finish)
            return
        result={'title':app.status.cget('text'),'has_preview':app.image is not None,
                'status': app.result.get('status') if app.result else 'failed',
                'max_count':app.result.get('max_count') if app.result else None,
                'input_region':app.result.get('input_region') if app.result else None,
                'generated_output':str(app.destination) if app.destination else None,
                'input':app.result.get('input') if app.result else None,
                'cleanup_enabled':app.delete_outputs.get(),
                'tkdnd':root.tk.call('package','present','tkdnd')}
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        exit_code[0]=0 if result['status']=='ok' and result['has_preview'] else 1
        app.close()
    root.after(100,finish)
    root.after(60000,lambda:app.close() if not app.closed else None)
    root.mainloop()
    sys.exit(exit_code[0])
else:
    main()
