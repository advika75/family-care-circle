"""One-command local demo of the web app with the REAL model (``make app-demo``), plus an optional demo seeder.

    python scripts/app_demo.py            # start the app: real model, persistent local demo database
    python scripts/app_demo.py --seed     # create an approved demo circle (SYNTHETIC data) in an EMPTY demo database

The demo database is ``app/var/demo.sqlite3`` (git-ignored, survives restarts) unless APP_DB_PATH is set.
It is deliberately separate from ``app/var/familycare.sqlite3`` so the seeder, which refuses to touch a database that
already has accounts, can never mix demo accounts into a database you use for real.
Nothing here makes an outbound network call; the port is chosen by trying to bind on 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "app" / "var" / "demo.sqlite3"
CREDENTIALS = ROOT / "app" / "var" / "demo_credentials.txt"      # app/var/ is git-ignored


def free_port(start: int = 8000, tries: int = 50) -> int:
    for port in range(start, start + tries):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No free port between {start} and {start + tries - 1}.")


def model_path() -> Path:
    from src.utils import load_config
    cfg = load_config(str(ROOT / "config.yaml"))
    path = Path(cfg["gguf_path"])
    return path if path.is_absolute() else ROOT / path


def check_model() -> Path:
    path = model_path()
    if not path.is_file():
        raise SystemExit(f"STOP: the model file is missing: {path}\n"
                         "Place the Qwen GGUF there (see README.md, 'Backends'), or run `make app-run` for the mock backend.")
    try:
        import llama_cpp  # noqa: F401
    except ImportError:
        raise SystemExit("STOP: llama-cpp-python is not installed in this Python, so the real model cannot run.\n"
                         "Activate the project's .venv, or run `make app-run` for the mock backend.")
    return path


def demo_env() -> dict[str, str]:
    env = dict(os.environ)
    env["APP_BACKEND"] = "llama_cpp"
    env.setdefault("APP_DB_PATH", str(DEFAULT_DB))
    return env


def run_server() -> int:
    model = check_model()
    env = demo_env()
    port = free_port()
    print("=" * 72)
    print("Family Care Circle: LOCAL DEMO with the real model. Synthetic data only.")
    print(f"  Address  : http://127.0.0.1:{port}")
    print(f"  Model    : {model}  ({model.stat().st_size / 1e9:.1f} GB)")
    print(f"  Database : {env['APP_DB_PATH']}  (kept between restarts)")
    print("  A note takes about 1 to 2 minutes to prepare; the page updates by itself.")
    print("  First run? create demo accounts with:  make app-demo-seed")
    print("  Stop with Ctrl+C.")
    print("=" * 72, flush=True)
    os.execvpe(sys.executable, [sys.executable, "-m", "uvicorn", "app.web.main:create_app", "--factory", "--host", "127.0.0.1",
                                "--port", str(port), "--no-server-header"], env)
    return 0


def run_seed(notes: int) -> int:
    env = demo_env()
    env["APP_BACKEND"] = "mock"          # seeding adds no notes by default; if it does, the mock keeps seeding instant
    if notes:
        env["APP_BACKEND"] = "llama_cpp"
        check_model()
    proc = subprocess.run([sys.executable, "-m", "app.dev_seed", "--notes", str(notes)], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode == 0:
        CREDENTIALS.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS.write_text(proc.stdout, encoding="utf-8")
        CREDENTIALS.chmod(stat.S_IRUSR | stat.S_IWUSR)
        print(f"\nThese passwords were saved ONCE to {CREDENTIALS} (owner-only, git-ignored). Delete that file when done.")
    return proc.returncode


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", action="store_true", help="create the synthetic demo circle in an empty demo database")
    ap.add_argument("--notes", type=int, default=0, help="with --seed: synthetic notes to generate now (default 0; slow with the real model)")
    args = ap.parse_args()
    sys.exit(run_seed(args.notes) if args.seed else run_server())
