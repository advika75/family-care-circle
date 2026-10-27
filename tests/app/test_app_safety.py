"""The child safety gate."""

from __future__ import annotations

import pytest

from app import safety

MEDS = ["Amoxicillin", "Ibuprofen", "Vitamin D 3"]


def test_clean_text_passes():
    # The child is a separate role from the patient, so child text speaks about the patient in the third person.
    text = ("Grandma has a sore throat. The doctors are helping her. Her medicine is like a team of tiny helpers. "
            "The grown-ups are taking care of her.")
    assert safety.check_child_text(text, MEDS) == []


@pytest.mark.parametrize("text", ["Take it for 3 days.", "Take 1 spoon.", "Room 5", "٣ days", "２ days"])  # incl. Unicode digits
def test_any_digit_withholds(text):
    assert safety.REASON_DIGIT in safety.check_child_text(text, MEDS)


@pytest.mark.parametrize("text", [
    "Your Amoxicillin helps.", "your amoxicillin helps.", "AMOXICILLIN!", "Take ibuprofen, then rest.",
    "It is (Ibuprofen) time.", "vitamin d 3 helps",
])
def test_medication_names_withhold_case_insensitively(text):
    assert safety.REASON_MEDICATION in safety.check_child_text(text, MEDS)


def test_medication_match_respects_word_boundaries():
    assert safety.check_child_text("An amoxicillinlike story.", MEDS) == []       # not a whole word
    # The child is a separate role from the patient, so child text speaks about the patient in the third person.
    assert safety.check_child_text("Her medicine helps her.", MEDS) == []         # the word "medicine" is fine


def test_only_this_notes_medications_are_checked():
    assert safety.check_child_text("A story about Ibuprofen.", ["Amoxicillin"]) == []


def test_sentence_limit_is_eight():
    ok = " ".join(f"Helper {w} is kind." for w in "alpha bravo charlie delta echo foxtrot golf hotel".split())
    assert safety.count_sentences(ok) == 8 and safety.check_child_text(ok, MEDS) == []
    nine = ok + " Helper india is kind."
    assert safety.count_sentences(nine) == 9 and safety.check_child_text(nine, MEDS) == [safety.REASON_TOO_LONG]


def test_sentences_are_counted_across_line_breaks_and_all_terminators():
    assert safety.count_sentences("One.\nTwo!\nThree? Four.") == 4
    assert safety.count_sentences("No terminator at all") == 1
    assert safety.count_sentences("") == 0


def test_all_reasons_are_reported_together():
    text = "Take Amoxicillin 3 times. " * 9
    assert safety.check_child_text(text, MEDS) == [safety.REASON_DIGIT, safety.REASON_MEDICATION, safety.REASON_TOO_LONG]


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_is_withheld(text):
    assert safety.check_child_text(text, MEDS) == [safety.REASON_EMPTY]


def test_medication_names_come_from_entities_and_regimens_longest_first():
    ents = [{"text": "Amoxicillin", "label": "MEDICATION"}, {"text": "500 mg", "label": "DOSAGE"},
            {"text": "Vitamin D", "label": "MEDICATION"}]
    regs = [{"medication": "Vitamin D 3"}, {"medication": "  "}]
    names = safety.medication_names(ents, regs)
    assert names == ["Amoxicillin", "Vitamin D 3", "Vitamin D"] and "500 mg" not in names      # equal lengths: alphabetical


def test_safe_message_is_the_specified_text_and_passes_its_own_gate():
    assert safety.SAFE_CHILD_MESSAGE == ("The note has information about someone's health. Their care team can explain what it means. "
                                         "You can ask a trusted adult if you have questions.")
    assert safety.check_child_text(safety.SAFE_CHILD_MESSAGE, MEDS) == []


def test_child_grounding_gate_rejects_unsupported_claims_and_medication_instructions():
    unsupported = safety.check_child_text("You had a heart attack.", MEDS, "Patient reports a mild cough.")
    assert safety.REASON_UNSUPPORTED_CLAIM in unsupported
    instruction = safety.check_child_text("You need to take special medicine.", MEDS, "Patient reports a mild cough.")
    assert safety.REASON_UNSUPPORTED_CLAIM in instruction


# ------------------------------------------------------------------------------------------ F-14 (Phase B)
MEDS2 = ["Amoxicillin", "Ibuprofen"]


@pytest.mark.parametrize("text,reason", [
    ("You take five milligrams every morning. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take ten of them, or a dozen. Rest well.", safety.REASON_NUMBER_WORD),
    ("You take it twice a day. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take it once a day. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take half of one. Rest well.", safety.REASON_NUMBER_WORD),
    ("A hundred small helpers. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take Twenty-Five of them. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take ninety-nine. Rest well.", safety.REASON_NUMBER_WORD),
    ("Take ① of them, then ² more. Rest well.", safety.REASON_DIGIT),
    ("Take ½ of one. Rest well.", safety.REASON_DIGIT),
    ("Take it for ３ days. Rest well.", safety.REASON_DIGIT),
    ("Some mg of it. Rest well.", safety.REASON_UNIT),
    ("A little MCG. Rest well.", safety.REASON_UNIT),
    ("Some ml of it. Rest well.", safety.REASON_UNIT),
    ("One tablet helps. Rest well.", safety.REASON_UNIT),
    ("The capsules help. Rest well.", safety.REASON_UNIT),
    ("A pill for you. Rest well.", safety.REASON_UNIT),
    ("Some units of it. Rest well.", safety.REASON_UNIT),
    ("You might die. The doctors are not sure.", safety.REASON_DENYLIST),
    ("It is a Cancer. Rest well.", safety.REASON_DENYLIST),
    ("A tumour was found. Rest well.", safety.REASON_DENYLIST),
    ("A tumor was found. Rest well.", safety.REASON_DENYLIST),
    ("It could be fatal. Rest well.", safety.REASON_DENYLIST),
    ("This is terminal. Rest well.", safety.REASON_DENYLIST),
    ("You need surgery. Rest well.", safety.REASON_DENYLIST),
    ("A long hospital stay. Rest well.", safety.REASON_DENYLIST),
    ("Death is scary. Rest well.", safety.REASON_DENYLIST),
    ("Grandpa is dying. Rest well.", safety.REASON_DENYLIST),
    ("Your Amoxicillin's job is to help. Rest well.", safety.REASON_MEDICATION),
    ("The amoxicillins will help. Rest well.", safety.REASON_MEDICATION),
    ("Your AMOXICILLIN’s job. Rest well.", safety.REASON_MEDICATION),
    ("Your amoxi​cillin helps. Rest well.", safety.REASON_MEDICATION),
    ("Your amoxi­cillin helps. Rest well.", safety.REASON_MEDICATION),
    ("and then " * 200, safety.REASON_TOO_LONG),
])
def test_f14_gate_catches(text, reason):
    assert reason in safety.check_child_text(text, MEDS2), text


def test_f14_run_on_text_without_punctuation_is_a_word_count_problem():
    assert safety.MAX_CHILD_WORDS == 120
    ok = " ".join(["rest"] * 120) + "."
    assert safety.REASON_TOO_LONG not in safety.check_child_text(ok, MEDS2)
    assert safety.REASON_TOO_LONG in safety.check_child_text(" ".join(["rest"] * 121) + ".", MEDS2)


def test_f14_stricter_sentence_splitter():
    assert safety.count_sentences("One; two: three. Four") == 4
    assert safety.count_sentences("One.Two.Three") == 3          # no space after the full stop
    assert safety.count_sentences("Wait... what? Yes!!") == 3


@pytest.mark.parametrize("text", [
    # The child is a separate role from the patient, so child text speaks about the patient in the third person.
    "Grandma is a bit sick. The doctors help her. She rests and drinks water. Her family is near. You can visit her.",
    # The child is a separate role from the patient, so child text speaks about the patient in the third person.
    "Her body is fighting germs. Sleep helps her body get strong. Grown-ups are taking care of her.",
    # The child is a separate role from the patient, so child text speaks about the patient in the third person.
    "Her medicine helps her body. She drinks water and rests. The nurse is kind.",
])
def test_f14_ordinary_child_text_still_passes(text):
    assert safety.check_child_text(text, MEDS2) == []


def test_f14_word_boundaries_for_new_lists():
    # words that merely CONTAIN a listed word must not trigger it
    assert safety.check_child_text("A dietary story about a deity. Rest well.", MEDS2) == []
    assert safety.check_child_text("Money tonight is not an issue, said the stone. Rest well.", MEDS2) == []
    assert safety.check_child_text("Your pillow is soft. Rest well.", MEDS2) == []
    assert safety.check_child_text("Surgeons are kind. Rest well.", MEDS2) == []
