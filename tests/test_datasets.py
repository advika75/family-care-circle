import json

import pytest

from src.datasets import dataset_config, load_annotation, prepare_mtsamples, select_note_files


def test_dataset_selection_and_seeded_subset(tmp_path):
    for name in ("a", "b", "c", "d"):
        (tmp_path / f"{name}.txt").write_text(name)
    assert dataset_config({"dataset": "mtsamples", "datasets": {"mtsamples": {"raw_dir": "external"}}})[
        "raw_dir"] == "external"
    first = select_note_files(tmp_path, 2, seed=19)
    assert first == select_note_files(tmp_path, 2, seed=19)
    assert len(first) == 2


def test_configured_datasets_keep_outputs_and_results_isolated():
    from src.utils import load_config

    config = load_config("config.yaml")
    synthetic = dataset_config(config)
    public = dataset_config({**config, "dataset": "mtsamples"})
    assert config["dataset"] == "synthetic"
    assert synthetic["outputs_dir"] == "data/outputs"
    assert synthetic["results_dir"] == "results"
    assert public["outputs_dir"] == "data/public/mtsamples/outputs"
    assert public["results_dir"] == "results/mtsamples"
    assert public["outputs_dir"] != synthetic["outputs_dir"]
    assert public["results_dir"] != synthetic["results_dir"]


def test_prepare_mtsamples_csv_selects_small_reproducible_subset(tmp_path):
    csv_path = tmp_path / "source.csv"
    csv_path.write_text('sample_name,transcription\nA,"note A"\nB,"note B"\nC,"note C"\n', encoding="utf-8")
    out = tmp_path / "notes"
    files = prepare_mtsamples(csv_path, out, limit=2, seed=5)
    assert len(files) == 2
    assert all(path.read_text().startswith("note ") for path in files)
    repeat = prepare_mtsamples(csv_path, tmp_path / "repeat", limit=2, seed=5)
    assert [path.name for path in files] == [path.name for path in repeat]
    assert [path.read_bytes() for path in files] == [path.read_bytes() for path in repeat]
    manifest = json.loads((out / "subset.json").read_text())
    assert manifest["seed"] == 5 and len(manifest["ids"]) == 2


def test_prepare_mtsamples_refuses_to_replace_existing_files(tmp_path):
    csv_path = tmp_path / "source.csv"
    csv_path.write_text('sample_name,transcription\nA,"note A"\n', encoding="utf-8")
    out = tmp_path / "notes"
    files = prepare_mtsamples(csv_path, out, limit=1, seed=5)
    before = {path.name: path.read_bytes() for path in out.iterdir()}

    with pytest.raises(FileExistsError, match="Refusing to replace existing MTSamples preparation files"):
        prepare_mtsamples(csv_path, out, limit=1, seed=5)

    assert before == {path.name: path.read_bytes() for path in out.iterdir()}


def test_prepare_mtsamples_requires_transcription_and_skips_empty_rows(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("sample_name,text\nA,valid\nB,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="transcription"):
        prepare_mtsamples(bad, tmp_path / "out")
    good = tmp_path / "good.csv"
    good.write_text("sample_name,transcription\nA,valid\nB,\nC,   \n", encoding="utf-8")
    files = prepare_mtsamples(good, tmp_path / "out", limit=10, seed=42)
    assert len(files) == 1 and files[0].name == "mtsamples_A.txt"


def test_load_annotation_reuses_span_json_and_checks_source(tmp_path):
    note = tmp_path / "note.txt"
    note.write_text("Take aspirin 5 mg.")
    gold = tmp_path / "note.json"
    gold.write_text(json.dumps({"id": "note", "source_file": "note.txt", "annotator": "test",
                               "entities": [{"text": "aspirin", "label": "MEDICATION", "start": 5, "end": 12}]}))
    assert load_annotation(gold, note)["entities"][0]["text"] == "aspirin"
    invalid = json.loads(gold.read_text())
    invalid["entities"][0]["start"] = 4
    gold.write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match="does not match"):
        load_annotation(gold, note)


def test_unknown_dataset_is_rejected():
    with pytest.raises(ValueError, match="Unknown dataset"):
        dataset_config({"dataset": "unknown", "datasets": {"synthetic": {}}})
