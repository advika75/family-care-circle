import json

import pytest

from scripts.annotate_mtsamples import AnnotationStore, PAGE


def _store(tmp_path):
    gold, notes = tmp_path / "gold", tmp_path / "notes"
    gold.mkdir()
    notes.mkdir()
    note_id = "mtsamples_demo"
    source_file = f"{note_id}.txt"
    (notes / source_file).write_text("Take aspirin 5 mg daily.", encoding="utf-8")
    (gold / "annotation_manifest.json").write_text(json.dumps({"seed": 42, "count": 1, "annotations": [
        {"id": note_id, "source_file": source_file, "status": "pending"}]}))
    (gold / f"{note_id}.json").write_text(json.dumps({"id": note_id, "source_file": source_file,
        "annotator": "", "entities": []}))
    return AnnotationStore(gold, notes), gold, note_id


def test_annotation_store_keeps_suggestions_separate_and_reads_state(tmp_path):
    store, _, note_id = _store(tmp_path)
    note = store.note(note_id)
    assert note["annotation"]["entities"] == []
    assert any(item["label"] == "MEDICATION" for item in note["suggestions"])
    assert store.state()["notes"][0]["status"] == "pending"


def test_annotation_store_save_validates_spans_and_updates_manifest(tmp_path):
    store, gold, note_id = _store(tmp_path)
    result = store.save({"id": note_id, "annotator": "Reviewer", "entities": [
        {"text": "aspirin", "label": "MEDICATION", "start": 5, "end": 12,
         "annotation_source": "accepted_suggestion"}]})
    assert result["entity_count"] == 1
    saved = json.loads((gold / f"{note_id}.json").read_text())
    manifest = json.loads((gold / "annotation_manifest.json").read_text())
    assert saved["annotator"] == "Reviewer" and saved["entities"][0]["text"] == "aspirin"
    assert saved["entities"][0]["annotation_source"] == "accepted_suggestion"
    assert manifest["annotations"][0]["status"] == "annotated"


def test_annotation_requires_explicit_review_to_mark_note_complete(tmp_path):
    store, gold, note_id = _store(tmp_path)
    with pytest.raises(ValueError, match="review_confirmed must be true"):
        store.complete(note_id, False)
    assert store.state()["notes"][0]["status"] == "pending"

    store.complete(note_id, True)
    assert store.state()["notes"][0]["status"] == "complete"

    # Any later edit removes the completion state until a reviewer confirms it again.
    store.save({"id": note_id, "entities": []})
    assert store.state()["notes"][0]["status"] == "annotated"


def test_annotation_store_rejects_mismatched_span(tmp_path):
    store, _, note_id = _store(tmp_path)
    with pytest.raises(ValueError, match="offsets/text"):
        store.save({"id": note_id, "entities": [{"text": "wrong", "label": "MEDICATION", "start": 5, "end": 12}]})


def test_character_offsets_are_python_codepoints_after_non_bmp_character():
    text = "A😀 aspirin"
    start = len("A😀 ")
    assert AnnotationStore._validate_entities(text, [{"text": "aspirin", "label": "MEDICATION",
                                                      "start": start, "end": start + 7}])[0]["start"] == 3
    with pytest.raises(ValueError, match="offsets/text"):
        AnnotationStore._validate_entities(text, [{"text": "aspirin", "label": "MEDICATION",
                                                    "start": 4, "end": 11}])


def test_annotation_ui_converts_browser_offsets_to_python_characters():
    assert "function cpLen(s){return Array.from(s).length;}" in PAGE
    assert "cpSlice(currentNote.text,o.start,o.end)" in PAGE
    assert "function domPointOffset(root,node,offset)" in PAGE


def test_annotation_ui_shows_keyboard_shortcuts_and_ignores_typing_targets():
    assert "Ctrl/⌘ S" in PAGE
    assert "Add selected suggestion <kbd>A</kbd>" in PAGE
    assert "<kbd>Delete</kbd> remove selected draft entity" in PAGE
    assert "function isTypingTarget(target){return target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(target.tagName);}" in PAGE
    assert "if(isTypingTarget(e.target))return;" in PAGE
    assert 'id="review-confirmed" type="checkbox"' in PAGE
    assert "Save and mark complete" in PAGE
    assert "api('/api/complete'" in PAGE


def test_annotation_shortcuts_require_explicit_suggestion_selection_and_entity_selection():
    assert "data-suggestion=\"${i}\"" in PAGE
    assert "$('add-suggestion').disabled=selectedSuggestionIndex===null;" in PAGE
    assert "key==='a'&&selectedSuggestionIndex!==null" in PAGE
    assert "selectedEntityIndex!==null){e.preventDefault();removeSelectedEntity();}" in PAGE
    assert "function addSuggestion(i)" in PAGE
    assert "function removeSelectedEntity()" in PAGE


def test_annotation_file_must_match_manifest_source_and_id(tmp_path):
    store, gold, note_id = _store(tmp_path)
    path = gold / f"{note_id}.json"
    annotation = json.loads(path.read_text())
    annotation["source_file"] = "another_note.txt"
    path.write_text(json.dumps(annotation))
    with pytest.raises(ValueError, match="source_file does not match manifest"):
        store.state()


def test_unprovenanced_suggestion_match_cannot_be_saved(tmp_path):
    store, _, note_id = _store(tmp_path)
    with pytest.raises(ValueError, match="explicit manual or accepted_suggestion provenance"):
        store.save({"id": note_id, "entities": [{"text": "aspirin", "label": "MEDICATION",
                                                   "start": 5, "end": 12}]})


def test_annotation_store_records_accepted_and_edited_suggestion_provenance(tmp_path):
    store, gold, note_id = _store(tmp_path)
    suggestions = store.note(note_id)["suggestions"]
    aspirin = next(e for e in suggestions if e["text"] == "aspirin")
    store.save({"id": note_id, "entities": [{**aspirin, "annotation_source": "accepted_suggestion"}]})
    saved = json.loads((gold / f"{note_id}.json").read_text())
    assert saved["entities"][0]["annotation_source"] == "accepted_suggestion"

    edited = {"text": "spirin", "label": "MEDICATION", "start": 6, "end": 12,
              "annotation_source": "edited_suggestion",
              "suggestion_reference": aspirin}
    store.save({"id": note_id, "entities": [edited]})
    saved = json.loads((gold / f"{note_id}.json").read_text())
    assert saved["entities"][0]["annotation_source"] == "edited_suggestion"
    assert saved["entities"][0]["suggestion_reference"]["text"] == "aspirin"


def test_blind_mode_hides_suggestions_and_only_records_manual_labels(tmp_path):
    _, gold, note_id = _store(tmp_path)
    blind = AnnotationStore(gold, gold.parent / "notes", blind=True)
    note = blind.note(note_id)
    assert note["suggestions"] == []
    assert blind.state()["blind_mode"] is True
    blind.save({"id": note_id, "entities": [{"text": "aspirin", "label": "MEDICATION",
                                               "start": 5, "end": 12, "annotation_source": "manual"}]})
    saved = json.loads((gold / f"{note_id}.json").read_text())
    assert saved["entities"][0]["annotation_source"] == "manual"


def test_blind_mode_rejects_suggestion_provenance(tmp_path):
    _, gold, note_id = _store(tmp_path)
    blind = AnnotationStore(gold, gold.parent / "notes", blind=True)
    with pytest.raises(ValueError, match="visible rule-based suggestion"):
        blind.save({"id": note_id, "entities": [{"text": "aspirin", "label": "MEDICATION",
                                                   "start": 5, "end": 12,
                                                   "annotation_source": "accepted_suggestion"}]})
