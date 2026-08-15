"""Compatibilidade: execução direta do dashboard em uma página Streamlit."""
import os
import runpy
from pathlib import Path

os.environ["FIO_CAIXA_EMBEDDED_DASHBOARD"] = "1"
dashboard_path = Path(__file__).resolve().parent.parent / "dashboard.py"
runpy.run_path(str(dashboard_path), run_name="__main__")
