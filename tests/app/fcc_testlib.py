"""Shared constants/helpers for the web-app tests (importable as ``fcc_testlib``)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

PASSWORD = "correct horse battery staple"  # synthetic test password, 28 chars


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


SOURCE_TEXT = (
    "ZEBRA-SOURCE-TOKEN visit note. Patient has strep throat.\n"
    "1. Amoxicillin 500 mg PO BID x 10 days.\n"
    "2. Ibuprofen 200 mg PO q6h PRN pain.\n"
)

CLEAN_CHILD = ("You have a sore throat. The doctors are helping you. Your medicine is like a team of tiny helpers. "
               "Rest and drink water. The grown-ups are taking care of you.")


def make_record(*, child: str = CLEAN_CHILD, valid: bool = True, patient: str | None = None,
                checklist: list[str] | None = None) -> dict:
    """A pipeline-shaped record (same keys as FamilyCarePipeline.run) with controllable content."""
    return {
        "id": "note-x",
        "patient_summary": patient or "You have strep throat. Take Amoxicillin 500 mg twice a day for 10 days. "
                                      "Take Ibuprofen 200 mg every 6 hours if you have pain.",
        "caregiver_checklist": checklist or ["Give Amoxicillin 500 mg twice a day for 10 days.",
                                             "Give Ibuprofen 200 mg every 6 hours if needed for pain.",
                                             "Call the care team if the fever returns."],
        "child_explanation": child,
        "entities": [
            {"text": "Amoxicillin", "label": "MEDICATION", "start": 60, "end": 71},
            {"text": "500 mg", "label": "DOSAGE", "start": 72, "end": 78},
            {"text": "BID", "label": "FREQUENCY", "start": 82, "end": 85},
            {"text": "10 days", "label": "DURATION", "start": 88, "end": 95},
            {"text": "Ibuprofen", "label": "MEDICATION", "start": 99, "end": 108},
        ],
        "regimens": [{"medication": "Amoxicillin", "dosages": ["500 mg"], "frequencies": ["BID"], "durations": ["10 days"]},
                     {"medication": "Ibuprofen", "dosages": ["200 mg"], "frequencies": ["q6h"], "durations": []}],
        "source_text": SOURCE_TEXT,
        "metadata": {
            "backend": "fake", "model_id": "fake-model", "model_hash": "sha256:abc", "seed": 1, "max_retries": 2,
            "retries": {"patient_summary": 1, "caregiver_checklist": 0, "child_explanation": 0},
            "missing_first_attempt": {"patient_summary": ["10 days"], "caregiver_checklist": [], "child_explanation": []},
            "missing_after_retries": {"patient_summary": [], "caregiver_checklist": [], "child_explanation": []},
            "fallback_used": {"patient_summary": False, "caregiver_checklist": False, "child_explanation": False},
            "truncated": {"patient_summary": False, "caregiver_checklist": False, "child_explanation": False},
            "redacted_dosages": {"patient_summary": [], "caregiver_checklist": [], "child_explanation": []},
            "valid": valid, "validation_errors": [] if valid else ["patient_summary must be a non-empty string"],
            "created_at": "2026-01-15T12:00:00+00:00",
        },
    }


class FakePipeline:
    """Stands in for FamilyCarePipeline: records calls and concurrency, and can fail or block on demand."""

    def __init__(self, record_factory=None, delay: float = 0.0, fail_with: Exception | None = None, gate=None) -> None:
        import threading
        self.record_factory = record_factory or (lambda text: make_record())
        self.delay, self.fail_with, self.gate = delay, fail_with, gate
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()
        self.on_run = None

    def run(self, text: str, doc_id: str = "doc") -> dict:
        import time
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.calls.append(doc_id)
        try:
            if self.gate is not None:
                self.gate.wait(5)
            if self.on_run:
                self.on_run(doc_id)
            if self.delay:
                time.sleep(self.delay)
            if self.fail_with:
                raise self.fail_with
            return self.record_factory(text)
        finally:
            with self._lock:
                self.active -= 1


# ---- HTML helpers (stdlib only) ---------------------------------------------------------------------------
import re as _re
from html.parser import HTMLParser as _HTMLParser


def csrf_from(html: str) -> str:
    m = _re.search(r'name="csrf_token" value="([0-9a-f]{64})"', html)
    assert m, "no csrf_token field in the page"
    return m.group(1)


class _Audit(_HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids, self.label_for, self.controls, self.h1 = set(), set(), [], 0
        self.inline_script, self.inline_style, self.handlers = False, False, []
        self.lang, self.landmarks, self.has_skip_link, self.aria_live = None, set(), False, False
        self._script_src = None
        self._label_depth = 0

    def handle_endtag(self, tag):
        if tag == "label" and self._label_depth:
            self._label_depth -= 1

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "label":
            self._label_depth += 1
            if "for" in a:
                self.label_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            # a control wrapped inside <label> is implicitly labelled (valid HTML)
            self.controls.append((tag, a.get("id"), a.get("aria-label") or ("wrapped" if self._label_depth else None)))
        if tag == "script":
            if "src" not in a:
                self.inline_script = True
        if "style" in a:
            self.inline_style = True
        if tag == "style":
            self.inline_style = True
        for k in a:
            if k.startswith("on"):
                self.handlers.append(k)
        if tag in ("main", "nav", "header", "footer"):
            self.landmarks.add(tag)
        if tag == "a" and a.get("class") == "skip-link":
            self.has_skip_link = True
        if a.get("aria-live") or a.get("role") in ("status", "alert"):
            self.aria_live = True


def audit_html(html: str) -> _Audit:
    p = _Audit()
    p.feed(html)
    return p


def assert_clean_page(html: str, *, expect_h1: bool = True) -> _Audit:
    """The structural/accessibility/CSP rules every rendered page must meet."""
    a = audit_html(html)
    assert a.lang == "en", "html lang"
    assert not a.inline_script and not a.inline_style and not a.handlers, ("inline script/style/handler", a.handlers)
    assert {"main", "nav", "header", "footer"} <= a.landmarks, a.landmarks
    assert a.has_skip_link
    if expect_h1:
        assert a.h1 == 1, f"{a.h1} <h1> elements"
    for tag, cid, aria in a.controls:
        assert aria or (cid and cid in a.label_for), f"<{tag} id={cid}> has no label"
    assert "Prototype. Not for real patient data." in html
    return a


SOURCE_MARK = "ZEBRA-SOURCE-TOKEN"
TITLE = "Clinic visit"
PATIENT_NAME = "Peggy Patientname"


# ---- picklable pipelines for tests that run the pipeline in a separate process ----------------------------------
class _TestPipeline:
    """Hangs forever on notes starting with 'hang', raises on 'boom', otherwise returns a normal record."""

    def run(self, text, doc_id="x"):
        import time
        if text.startswith("hang"):
            time.sleep(3600)
        if text.startswith("boom"):
            raise RuntimeError("PRIVATE-FRAGMENT 123-45-6789")
        return make_record()


class TestPipelineFactory:
    """A top-level (picklable) zero-argument factory, as required by a spawned worker process."""

    def __call__(self):
        return _TestPipeline()
