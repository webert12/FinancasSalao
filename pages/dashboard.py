"""Página do sistema de Salão de Beleza.

O Render continua iniciando app.py. Esta página interna apenas executa o
dashboard.py original quando o usuário escolhe "Salão de Beleza".
"""

import runpy
from pathlib import Path

dashboard_path = Path(__file__).resolve().parent.parent / "dashboard.py"
runpy.run_path(str(dashboard_path), run_name="__main__")
