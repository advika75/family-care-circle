"""Real-model check of the note-length limit (F-02). Needs models/qwen2.5-3b-instruct-q4_k_m.gguf and takes minutes.

Marked ``realmodel``: skipped unless ``APP_RUN_SLOW=1``. Measured with the real tokenizer (see app/README.md): the
densest realistic synthetic note needs 3,624 of the 4,096 context tokens at 6,000 characters on its worst retry, and the
real model's retry prompt stops fitting between 7,000 and 8,000 characters.
"""

from __future__ import annotations

import pytest

from app import accounts, circle, notes
from app.config import REPO_ROOT, Settings
from app.context import Ctx
from app.db import connect, migrate
from app.errors import ValidationFailed
from app.jobs import JobRunner

pytestmark = pytest.mark.realmodel
MODEL = REPO_ROOT / "models" / "qwen2.5-3b-instruct-q4_k_m.gguf"


def _dense_note(n: int) -> str:
    seed = (REPO_ROOT / "data" / "raw" / "note_07.txt").read_text(encoding="utf-8")         # densest of the synthetic notes
    return ("\n".join([seed] * (n // len(seed) + 2)))[:n]


@pytest.mark.skipif(not MODEL.exists(), reason="model file not present")
def test_a_note_at_the_limit_finishes_with_the_real_model_and_a_longer_one_is_refused_up_front(tmp_path):
    s = Settings(db_path=tmp_path / "r.sqlite3", backend="llama_cpp", scrypt_n=16, secret_key=b"k" * 32)
    ctx = Ctx(s)
    conn = connect(s.db_path); migrate(conn)
    runner = JobRunner(s, ctx)
    u = accounts.signup(conn, ctx, email="o@example.test", display_name="O", password="a long enough password")
    p = circle.create_profile(conn, ctx, u, display_name="P", relationship_label="Son")
    with pytest.raises(ValidationFailed) as e:
        notes.add_note(conn, ctx, runner, u, p, title="too long", text=_dense_note(s.max_note_chars + 1))
    assert "too long for the local model" in e.value.errors["text"]
    notes.add_note(conn, ctx, runner, u, p, title="at the limit", text=_dense_note(s.max_note_chars))
    runner.drain()
    row = conn.execute("SELECT status, error_message FROM notes").fetchone()
    runner.shutdown()
    assert (row["status"], row["error_message"]) == ("done", None)
    assert conn.execute("SELECT COUNT(*) FROM outputs").fetchone()[0] == 1
