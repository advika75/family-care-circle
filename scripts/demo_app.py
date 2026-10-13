"""Local Streamlit demo: pick or paste a clinical note, see extracted entities highlighted by label,
the three persona outputs side by side, retention/retry/fallback status and hallucination flags.

Local inference only; nothing here calls a commercial API. Loads the model once per session (not on
every rerun), so it runs on an 8 GB M1 with the quantized llama.cpp backend.

Run from the project root:
    streamlit run scripts/demo_app.py                         # real model, backend from config.yaml
    streamlit run scripts/demo_app.py -- --mock-backend        # no model download or inference, instant UI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src.demo import highlight_entities, persona_badges, persona_output_text, ENTITY_COLORS  # noqa: E402
from src.pipeline import FamilyCarePipeline  # noqa: E402
from src.prompts import PERSONAS  # noqa: E402
from src.reporting import PRETTY  # noqa: E402
from src.utils import load_config, resolve_path  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse the demo's own flags (passed after `--` to `streamlit run`)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock-backend", action="store_true", help="Use the mock backend: no model, instant")
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args(sys.argv[1:])


@st.cache_resource(show_spinner=False)
def load_pipeline(mock: bool, config_path: str) -> FamilyCarePipeline:
    """Build the pipeline once per session; st.cache_resource keeps the loaded model across reruns."""
    overrides = {"backend": "mock"} if mock else {}
    return FamilyCarePipeline(load_config(config_path, overrides))


def render_persona_column(record: dict, persona: str, source: str) -> None:
    st.markdown(f"**{PRETTY.get(persona, persona)}**")
    st.text(persona_output_text(record, persona))
    badges = persona_badges(record, persona, source)
    for b in badges:
        st.caption(b)
    if not badges:
        st.caption("✅ clean: no retries, fallback or flags")


def main(args: argparse.Namespace) -> None:
    st.set_page_config(page_title="Family Care Circle Demo", layout="wide")
    st.title("Family Care Circle — demo")
    st.caption(
        "Research prototype, not medical advice, not for clinical use. "
        + ("Mock backend: no model, text is templated from extracted entities."
           if args.mock_backend else "Local inference only (llama.cpp); no commercial API is called.")
    )

    raw_dir = resolve_path("data/raw")
    note_files = sorted(raw_dir.glob("*.txt")) if raw_dir.is_dir() else []
    options = ["(paste your own)"] + [p.name for p in note_files]
    choice = st.sidebar.selectbox("Note", options)
    if choice == "(paste your own)":
        text = st.sidebar.text_area("Paste a clinical note", height=240, key="pasted_note")
    else:
        text = (raw_dir / choice).read_text(encoding="utf-8")
        st.sidebar.text_area("Note preview", text, height=240, disabled=True)

    run = st.sidebar.button("Generate", type="primary")
    if run:
        if not text.strip():
            st.sidebar.error("Pick a note or paste one first.")
        else:
            spinner_msg = ("Running the mock pipeline..." if args.mock_backend else
                            "Loading the model (first run only) and generating... this can take a minute on an "
                            "8 GB M1.")
            with st.spinner(spinner_msg):
                pipeline = load_pipeline(args.mock_backend, args.config)
                st.session_state["record"] = pipeline.run(text, doc_id="demo")
                st.session_state["source"] = text

    record = st.session_state.get("record")
    if record is None:
        st.info("Pick or paste a note in the sidebar, then click Generate.")
        return

    source = st.session_state["source"]
    st.subheader("Extracted entities")
    st.markdown(
        f'<div style="white-space:pre-wrap;line-height:1.6;border:1px solid #ddd;border-radius:6px;'
        f'padding:14px;max-height:320px;overflow:auto">{highlight_entities(source, record["entities"])}</div>',
        unsafe_allow_html=True,
    )
    legend = " ".join(
        f'<span style="background:{color};padding:1px 6px;border-radius:3px;margin-right:6px">{label}</span>'
        for label, color in ENTITY_COLORS.items()
    )
    st.markdown(legend, unsafe_allow_html=True)

    st.subheader("Persona outputs")
    for col, persona in zip(st.columns(len(PERSONAS)), PERSONAS):
        with col:
            render_persona_column(record, persona, source)


if __name__ == "__main__":
    main(parse_args())
