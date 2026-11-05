import json
from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image

from scanner.evaluation import normalize_text, score_text, summarize
from scripts.evaluate_benchmark import load_samples
from scripts.generate_benchmark import CONDITIONS, make_scene


@pytest.mark.parametrize(
    "reference,hypothesis,edits",
    [
        ("abc", "axc", 1),
        ("abc", "ab", 1),
        ("abc", "abcc", 1),
        ("abc", "", 3),
        ("a", "xyz", 3),
        ("kitten", "sitting", 3),
        ("ABC", "abc", 3),
        ("O‘quv", "Oquv", 1),
        ("번호: 123", "번호:123", 1),
        ("한", "한", 0),
        ("one\n  two", "one two", 0),
    ],
)
def test_character_edit_distance(reference, hypothesis, edits):
    score = score_text(reference, hypothesis)
    assert score.edits == edits
    assert score.cer == pytest.approx(edits / len(normalize_text(reference)))


def test_empty_reference_is_rejected_and_cer_can_exceed_one():
    with pytest.raises(ValueError, match="non-empty"):
        score_text(" \n", "output")
    assert score_text("a", "xyz").cer == 3


def test_micro_cer_weights_reference_lengths():
    def record(length, edits):
        return {
            "language": "en",
            "mode": "auto_scan",
            "reference_characters": length,
            "edits": edits,
            "inference_seconds": 2,
            "total_seconds": 3,
            "detected": True,
            "used_original": False,
        }

    summary = summarize([record(1, 1), record(9, 0)])[0]
    assert summary["cer"] == 0.1  # not the unweighted page mean of 0.5
    assert summary["documents"] == 2


def manifest_fixture(tmp_path):
    image = BytesIO()
    Image.new("RGB", (40, 40), "white").save(image, "PNG")
    (tmp_path / "image.png").write_bytes(image.getvalue())
    (tmp_path / "text.txt").write_text("O‘quv 한국어", encoding="utf-8")
    item = {
        "id": "one",
        "language": "uz",
        "condition": "clean",
        "image": "image.png",
        "reference": "text.txt",
        "image_sha256": sha256(image.getvalue()).hexdigest(),
        "reference_sha256": sha256((tmp_path / "text.txt").read_bytes()).hexdigest(),
    }
    return {"version": 1, "samples": [item]}


def test_manifest_loads_verified_unicode_ground_truth(tmp_path):
    manifest = manifest_fixture(tmp_path)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    _, samples = load_samples(path)
    assert samples[0]["reference_text"] == "O‘quv 한국어"


@pytest.mark.parametrize(
    "problem", ["checksum", "duplicate", "traversal", "language", "empty_reference"]
)
def test_bad_dataset_is_rejected_before_models_load(tmp_path, problem):
    manifest = manifest_fixture(tmp_path)
    entry = manifest["samples"][0]
    if problem == "checksum":
        entry["image_sha256"] = "bad"
    elif problem == "duplicate":
        manifest["samples"].append(entry.copy())
    elif problem == "traversal":
        entry["image"] = "../image.png"
    elif problem == "language":
        entry["language"] = "unsupported"
    else:
        (tmp_path / "text.txt").write_text("  ")
        entry["reference_sha256"] = sha256((tmp_path / "text.txt").read_bytes()).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_samples(path)


def test_all_scene_conditions_are_deterministic_and_do_not_mutate_page():
    import numpy as np

    page = np.full((200, 300, 3), 255, dtype=np.uint8)
    for condition in CONDITIONS:
        first, corners = make_scene(page, condition)
        second, _ = make_scene(page, condition)
        assert np.array_equal(first, second)
        assert (corners is None) == (condition == "clean")
    assert np.all(page == 255)
