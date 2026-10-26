"""Start the app:  python run.py   (extra arguments go to Streamlit, e.g. --server.port 9000)"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Streamlit is not installed. Run:  pip install -r requirements.txt")
        return 1

    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"), *sys.argv[1:]]
    try:
        return subprocess.call(cmd, cwd=ROOT)  # cwd keeps chat_history/ inside the project
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
