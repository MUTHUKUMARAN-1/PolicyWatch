"""Root launcher for PTCT Web Application.
Allows running `python run.py` directly from workspace root.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
PTCT_DIR = ROOT_DIR / "ptct-scraper"

if str(PTCT_DIR) not in sys.path:
    sys.path.insert(0, str(PTCT_DIR))

os.chdir(str(PTCT_DIR))

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1")
    print(f"\n=======================================================")
    print(f" [PTCT] Privacy Policy & Terms Change Tracker Web App")
    print(f" Server running at: http://{host}:{port}")
    print(f" Default Admin: admin / Admin@PTCT2026!")
    print(f"=======================================================\n")
    app.run(host=host, port=port, debug=debug)

