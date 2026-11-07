"""The overview question set and scripts/eval_overview.py.

None of this scores anything: the metrics are pure functions tested on made-up spans, the context builder
is run on a tiny repository written into a temporary folder, and the question files are checked for
shape. What the script reports on the real sets is recorded in docs/RESULTS.md, not asserted here.
"""

import json
import re
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import eval_overview as eo  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions"
OVERVIEW = QUESTIONS / "overview"
CACHE = ROOT / ".codeatlas" / "eval-repos"

STARTERS = [
    "Summarize what this codebase does",
    "What are the most important files?",
    "Show me the architecture overview",
    "What frameworks and libraries are used?",
]


def _sets():
    return [eo.load_overview_set(p) for p in sorted(OVERVIEW.glob("*.json"))]


def _normal(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _words(text: str) -> set[str]:
    return set(_normal(text).split())


# ---- the question files ------------------------------------------------------------------------


def test_there_are_two_repositories_with_eight_questions_each():
    sets = _sets()
    assert sorted(s.name for s in sets) == ["flask", "itsdangerous"]
    for s in sets:
        assert len(s.questions) == 8, s.name
        assert sorted(q.split for q in s.questions) == ["dev"] * 4 + ["test"] * 4, s.name


def test_ids_are_unique_across_both_files():
    ids = [q.id for s in _sets() for q in s.questions]
    assert len(ids) == len(set(ids)) == 16


def test_each_repository_is_pinned_to_the_commit_the_other_sets_use():
    for s in _sets():
        other = json.loads((QUESTIONS / f"{s.name}.json").read_text(encoding="utf-8"))
        assert s.commit == other["commit"], s.name
        assert s.repo_url == other["repo_url"], s.name


def test_the_four_starter_questions_are_there_verbatim_in_both_repositories():
    for s in _sets():
        asked = {q.question for q in s.questions}
        assert set(STARTERS) <= asked, s.name


def test_four_paraphrases_make_up_the_rest():
    for s in _sets():
        paraphrases = [q for q in s.questions if q.question not in STARTERS]
        assert len(paraphrases) == 4, s.name


def test_every_core_file_has_a_reason_and_expected_files_repeat_them():
    for s in _sets():
        for q in s.questions:
            assert q.core_files, q.id
            assert all(reason.strip() for reason in q.core_files.values()), q.id
            raw = json.loads((OVERVIEW / f"{s.name}.json").read_text(encoding="utf-8"))
            expected = next(r["expected_files"] for r in raw["questions"] if r["id"] == q.id)
            assert expected == list(q.core_files), q.id


def test_only_the_dependency_questions_name_manifest_files():
    for s in _sets():
        for q in s.questions:
            if q.topic == "deps":
                # itsdangerous's README names no dependency, so only its pyproject (which declares none) is listed.
                expected = {"pyproject.toml"} if s.name == "itsdangerous" else {"pyproject.toml", "README.md"}
                assert set(q.manifest_files) == expected, q.id
                assert all(reason.strip() for reason in q.manifest_files.values()), q.id
            else:
                assert q.manifest_files == {}, q.id


def test_each_topic_is_in_both_splits():
    for s in _sets():
        by_topic = {}
        for q in s.questions:
            by_topic.setdefault(q.topic, set()).add(q.split)
        # read_first and files are one topic to a reader; the rest are asked once per split.
        assert by_topic["summary"] == by_topic["arch"] == by_topic["deps"] == {"dev", "test"}, s.name


@pytest.mark.skipif(not CACHE.exists(), reason="the pinned checkouts are fetched by scripts/eval_retrieval.py")
def test_expected_and_manifest_files_exist_in_the_pinned_checkouts():
    checked = 0
    for s in _sets():
        root = CACHE / f"{s.name}-{s.commit[:12]}"
        if not root.exists():
            continue
        for q in s.questions:
            for path in [*q.core_files, *q.manifest_files]:
                assert (root / path).is_file(), f"{q.id}: {path} is not in {root.name}"
                checked += 1
    if not checked:
        pytest.skip("no pinned checkout is present")


def _earlier_questions() -> list[str]:
    texts = []
    for path in QUESTIONS.rglob("*.json"):
        if OVERVIEW in path.parents:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["questions"] if isinstance(data, dict) else data
        texts.extend(item["question"] for item in items if isinstance(item, dict) and "question" in item)
    return texts


def test_no_overview_question_repeats_or_closely_paraphrases_an_earlier_set():
    earlier = _earlier_questions()
    assert len(earlier) >= 60, "the earlier sets were not found, so this test would pass for nothing"
    for s in _sets():
        for q in s.questions:
            mine = _words(q.question)
            for old in earlier:
                if _normal(old) == _normal(q.question):
                    pytest.fail(f"{q.id} repeats an earlier question: {old!r}")
                theirs = _words(old)
                overlap = len(mine & theirs) / len(mine | theirs)
                assert overlap < 0.6, f"{q.id} is a close paraphrase of {old!r} ({overlap:.2f})"


# ---- the metrics -------------------------------------------------------------------------------


def test_core_coverage_counts_each_file_once_however_many_spans_it_has():
    files = ["a.py", "a.py", "b.py", "x.py"]
    assert eo.core_coverage(files, ["a.py", "b.py", "c.py", "d.py"]) == 0.5


def test_core_coverage_of_nothing_required_is_one_and_of_an_empty_context_is_zero():
    assert eo.core_coverage(["a.py"], []) == 1.0
    assert eo.core_coverage([], ["a.py"]) == 0.0


def test_a_test_file_a_docs_file_and_an_overlapping_span_are_noise_and_the_rest_is_not():
    spans = [
        ("src/pkg/signer.py", 10, 40),
        ("tests/test_signer.py", 1, 5),
        ("docs/conf.py", 1, 46),
        ("src/pkg/signer.py", 30, 60),  # overlaps the first slot
        ("src/pkg/signer.py", 61, 70),  # touches nothing earlier
        ("src/pkg/timed.py", 10, 40),  # same lines, a different file
    ]
    assert eo.noise_slots(spans) == ["", "test", "docs", "overlap", "", ""]
    assert eo.noise_share(eo.noise_slots(spans)) == 0.5


def test_adjacent_spans_that_share_no_line_are_not_an_overlap():
    assert eo.noise_slots([("a.py", 1, 10), ("a.py", 11, 20)]) == ["", ""]


def test_the_same_span_twice_is_an_overlap():
    assert eo.noise_slots([("a.py", 5, 9), ("a.py", 5, 9)]) == ["", "overlap"]


def test_an_empty_context_has_no_noise():
    assert eo.noise_share([]) == 0.0


def test_a_conftest_and_a_tests_folder_count_as_tests_like_the_search_setting_says():
    assert eo.noise_slots([("tests/helpers.py", 1, 2), ("pkg/conftest.py", 1, 2)]) == ["test", "test"]


# ---- the context builder: deterministic, and no model or network -------------------------------


def _tiny_repo(root: Path) -> None:
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "pkg" / "signer.py").write_text(
        "class Signer:\n    def sign(self, value):\n        return value + '.sig'\n\n"
        "    def unsign(self, signed):\n        return signed.rsplit('.', 1)[0]\n",
        encoding="utf-8",
    )
    (root / "src" / "pkg" / "timed.py").write_text(
        "def add_timestamp(value, now):\n    return f'{value}@{now}'\n", encoding="utf-8"
    )
    (root / "tests" / "test_signer.py").write_text("def test_sign():\n    assert True\n", encoding="utf-8")


def _build(tmp_path: Path):
    _tiny_repo(tmp_path)
    answers, *_ = eo.build_answers(tmp_path, "tiny", "tiny", "0" * 40)
    return eo.RetrievalAgent(answers)


def test_the_context_is_the_same_twice_and_makes_no_network_call(tmp_path, monkeypatch):
    agent = _build(tmp_path)

    def refuse(*args, **kwargs):
        raise AssertionError("the overview context tried to open a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    first = eo.context_for(agent, "What does this project do?", "tiny", tmp_path)
    second = eo.context_for(agent, "What does this project do?", "tiny", tmp_path)
    assert first == second
    assert first["spans"], "the tiny repository should have produced a context"
    assert first["prompt_chars"] > 0


def test_context_paths_are_relative_to_the_checkout(tmp_path):
    agent = _build(tmp_path)
    spans = eo.context_for(agent, "sign unsign", "tiny", tmp_path)["spans"]
    assert all(not Path(path).is_absolute() for path, _, _ in spans)
    assert any(path == "src/pkg/signer.py" for path, _, _ in spans)


def test_the_prompt_is_the_mentors_prompt_over_the_numbered_snippets(tmp_path):
    from codeatlas.services.agents.coding_mentor_agent import _SYSTEM

    agent = _build(tmp_path)
    retrieved = agent.locate("sign unsign", "tiny", top_k=eo.TOP_K)
    context = eo.context_for(agent, "sign unsign", "tiny", tmp_path)
    expected = len(_SYSTEM) + len(f"Code snippets:\n{eo._numbered(retrieved.snippets)}\n\nQuestion: sign unsign")
    assert context["prompt_chars"] == expected


def test_score_question_reports_coverage_noise_and_manifest_separately(tmp_path):
    question = eo.OverviewQuestion(
        id="q",
        split="dev",
        question="What does it depend on?",
        topic="deps",
        core_files={"src/pkg/signer.py": "why"},
        manifest_files={"pyproject.toml": "why", "README.md": "why"},
    )
    row = eo.score_question(
        question,
        {"spans": [("src/pkg/signer.py", 1, 3), ("tests/test_x.py", 1, 2)], "prompt_chars": 100},
    )
    assert row["core"] == 1.0
    assert row["noise"] == 0.5
    assert row["manifest"] == 0.0  # not indexed, so never present


def test_a_missing_checkout_is_refused_rather_than_fetched(tmp_path):
    some = eo.OverviewSet(name="nope", repo_url="https://example.invalid/x", commit="a" * 40, questions=[])
    with pytest.raises(SystemExit) as raised:
        eo.find_checkout(some, tmp_path)
    assert "no network call" in str(raised.value)


def test_the_script_does_not_import_a_network_or_model_client():
    source = (ROOT / "scripts" / "eval_overview.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "httpx", "urllib", "langchain_groq", "openai", "subprocess"):
        assert f"import {forbidden}" not in source and f"from {forbidden}" not in source, forbidden
