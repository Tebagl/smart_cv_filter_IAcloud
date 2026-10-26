"""
Prueba visual de alertas 503, sin tocar el código de producción.

analyzer.py hace `import time` y `import requests`. Hay que parchear
`src.backend.analyzer.time.sleep` y `src.backend.analyzer.requests.post`.

Uso (desde la raíz del proyecto, con el venv activo):

    python tests/test_alertas_gui.py

Pulsa «CLASIFICAR CVS». Los 5 CVs agotan 5 reintentos 503 cada uno en
fracciones de segundo (el log puede seguir diciendo «Esperando 10s»,
pero el sleep está anulado). Tras el 5.º salta la pausa automática.
Pulsa «Reanudar análisis» para terminar el lote.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


class _Respuesta503:
    status_code = 503
    headers = {}
    text = "Service Unavailable"

    def json(self):
        return {"error": {"code": 503, "message": "Service Unavailable"}}


def _post_503(*_args, **_kwargs):
    return _Respuesta503()


def _preparar_carpetas():
    tmp = Path(tempfile.mkdtemp(prefix="alertas_gui_"))
    entrada = tmp / "entrada"
    destino = tmp / "procesos"
    entrada.mkdir()
    destino.mkdir()
    for i in range(1, 6):
        (entrada / f"cv_prueba_alertas_{i}.txt").write_text(
            f"Candidato de prueba {i}. Experiencia en hostelería y atención al cliente.\n",
            encoding="utf-8",
        )
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    return entrada, destino


def _aplicar_mocks(analyzer_mod, main_gui_mod):
    # analyzer.py: `import time` → time.sleep(...)
    analyzer_mod.time.sleep = lambda _s=None: None
    # analyzer.py: `import requests` → requests.post(...)
    analyzer_mod.requests.post = _post_503
    # main_gui.py: `import time` → _interruptible_sleep (4,5 s entre CVs)
    main_gui_mod.time.sleep = lambda _s=None: None


def _precargar_formulario(app, entrada: Path, destino: Path):
    app.input_folder.set(str(entrada))
    app.entry_destino.delete(0, "end")
    app.entry_destino.insert(0, str(destino))
    app.entry_puesto.delete(0, "end")
    app.entry_puesto.insert(0, "Prueba alertas 503")
    app.jd_textbox.delete("0.0", "end")
    app.jd_textbox.insert(
        "0.0",
        "Puesto de prueba para validar el aviso audiovisual de saturación del servidor.",
    )

    original = app.run_analysis

    def run_analysis_una_vez(*_a, **_k):
        if app.analyzing or str(app.btn_analyze.cget("state")) == "disabled":
            return
        app.btn_analyze.configure(state="disabled")
        return original(*_a, **_k)

    app.run_analysis = run_analysis_una_vez
    app.btn_analyze.configure(command=run_analysis_una_vez)
    app._interruptible_sleep = lambda _s=None: None

    app.log_mensaje(
        "🧪 Mock activo: requests.post → 503, time.sleep anulado en analyzer y GUI. "
        "Pulsa CLASIFICAR CVS (el botón se bloquea al primer clic). "
        "El log puede decir «Esperando 10s» pero no espera. Tras 5 CVs, pausa automática."
    )


def main():
    from src.frontend import main_gui
    import src.backend.analyzer as analyzer_mod

    _aplicar_mocks(analyzer_mod, main_gui)

    entrada, destino = _preparar_carpetas()
    print(f"Entrada de prueba: {entrada}")
    print(f"Destino de prueba: {destino}")
    print("Pulsa CLASIFICAR CVS. Sleeps anulados: los 5 CVs deben saturar en < 3 s.")

    app = main_gui.SmartCVFilterApp()
    app.after(250, lambda: _precargar_formulario(app, entrada, destino))
    app.mainloop()


if __name__ == "__main__":
    main()
