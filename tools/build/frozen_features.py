"""Packaged GUI feature integration check, invoked only by --features-test."""
import time
from pathlib import Path

def check_features(app,report):
    from lumina_route_finder.ui.preferences import PreferencesDialog
    from lumina_route_finder.ui.recognition_inspector import RecognitionInspector
    from lumina_route_finder.ui.diagnostics_dialog import DiagnosticsDialog
    from lumina_route_finder.desktop.route_export import save_candidate,dib_bytes
    root=app.root
    dialog=PreferencesDialog(app);root.update_idletasks()
    assert len(dialog.weight_vars)==12
    dialog.window.destroy()
    inspector=RecognitionInspector(app);root.update_idletasks()
    assert len(inspector.nodes.get_children())==50
    original=inspector.editor.snapshot.labels[(0,0)]
    inspector.editor.set_label((0,0),'escape_room');inspector.editor.undo()
    assert inspector.editor.snapshot.labels[(0,0)]==original
    inspector.window.destroy()
    dialog=DiagnosticsDialog(app)
    deadline=time.monotonic()+5
    while not dialog.rows and time.monotonic()<deadline:root.update();time.sleep(.01)
    assert dialog.rows and dialog.rows[0]['result']['status']=='ok'
    dialog.close()
    app.focus_step(0)
    image=app.candidate_image()
    assert image.shape==(1000,520,3) and dib_bytes(image)
    path=Path(report).parent/'feature-export.png'
    save_candidate(path,app.board,app.result,app.page,app.output_root,app.selected_step)
    assert path.is_file()
    app.start(limit=1)  # Finish callback will verify this reuses recognition.
