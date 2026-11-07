"""Score the context an overview question would send to the model: which files it draws on, and how much of it is noise.

    python scripts/eval_overview.py --split dev
    python scripts/eval_overview.py --split test        # the held-out half: score it once

Retrieval only. No model, no network, no key, nothing written. The two pinned repositories must already be
checked out in --cache-dir (default .codeatlas/eval-repos, the cache scripts/eval_retrieval.py fills); this
script refuses to fetch rather than make a network call.

**What "the context" is.** The default chat path (`ask_controller._ask_stream`, repo mode) does
`orchestrator.search(question, repo_id)`, which is `RetrievalAgent.locate`, which is `AnswerService.locate`
(top_k 5, no model call); it then asks `CodingMentorAgent.answer`, which formats `_PROMPT` with the snippets
numbered by `_numbered`. This script calls `RetrievalAgent.locate` over an `AnswerService` built exactly as
`scripts/eval_retrieval.py` builds one, and formats `_PROMPT` with `_numbered`. What differs from the server:

* the follow-up rewrite (`_search_question`) is skipped, because an overview question starts a session
  and has no history, so the server skips it too;
* the index here is in memory and built straight from the checkout, as the retrieval eval does, not
  loaded from `.codeatlas/indexes`;
* `_PROMPT` and `_numbered` are private names imported across a module boundary, because no public function
  returns the final prompt - it is assembled inside `CodingMentorAgent.answer`, in the same call that
  invokes the model, so there is nothing to call that stops short of it;
* the settings are `load_config()`'s, so an operating-system environment variable named CODEATLAS_* changes
  them; the effective ones are printed first.

**Metrics, per question.**

* core-file coverage: core files present in the context / core files. A file counts once however many of
  its spans are in the context.
* noise share: the share of the context's slots that are a test file, a file under docs/, or a span that
  overlaps an earlier slot of the same file (the same code twice).
* manifest coverage: manifest files present / manifest files, reported separately. It is zero for any
  file the server does not index (pyproject.toml, README.md) by construction; it exists so that a change
  that starts indexing them has somewhere to show up.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codeatlas.app.di import build_embedder, index_options, retrieval_settings_for  # noqa: E402
from codeatlas.models.repository import Repository  # noqa: E402
from codeatlas.services.agents.coding_mentor_agent import _PROMPT, _numbered  # noqa: E402
from codeatlas.services.agents.retrieval_agent import RetrievalAgent  # noqa: E402
from codeatlas.services.parsing.tree_sitter_parser import TreeSitterAstParser  # noqa: E402
from codeatlas.services.qa.answer_service import AnswerService, _is_test_path  # noqa: E402
from codeatlas.services.retrieval.faiss_retriever import FaissCodeRetriever  # noqa: E402
from codeatlas.services.retrieval.indexing import CodeIndexService  # noqa: E402
from codeatlas.utils.config import load_config  # noqa: E402

QUESTIONS_DIR = ROOT / "eval" / "questions" / "overview"
DEFAULT_SETS = [QUESTIONS_DIR / "itsdangerous.json", QUESTIONS_DIR / "flask.json"]
SPLITS = ("dev", "test", "all")
TOP_K = 5  # what the default path asks for: orchestrator.search -> RetrievalAgent.locate(top_k=5)


@dataclass(frozen=True)
class OverviewQuestion:
    id: str
    split: str
    question: str
    topic: str
    core_files: dict[str, str]
    manifest_files: dict[str, str]


@dataclass(frozen=True)
class OverviewSet:
    name: str
    repo_url: str
    commit: str
    questions: list[OverviewQuestion]


def load_overview_set(path: Path) -> OverviewSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = [
        OverviewQuestion(
            id=q["id"],
            split=q["split"],
            question=q["question"],
            topic=q["topic"],
            core_files=dict(q["core_files"]),
            manifest_files=dict(q.get("manifest_files", {})),
        )
        for q in data["questions"]
    ]
    return OverviewSet(name=data["name"], repo_url=data["repo_url"], commit=data["commit"], questions=questions)


# ---- metrics: pure functions, so they can be tested without an index ---------------------------


def core_coverage(files_in_context: list[str], core_files: list[str] | set[str]) -> float:
    """Share of the core files that appear anywhere in the context. 1.0 for an empty core list."""
    core = set(core_files)
    if not core:
        return 1.0
    return len(core & set(files_in_context)) / len(core)


def is_docs_path(path: str) -> bool:
    parts = Path(path.replace("\\", "/")).parts
    return bool(parts) and parts[0] in ("docs", "doc")


def noise_slots(spans: list[tuple[str, int, int]]) -> list[str]:
    """For each (path, start, end) slot in order: '' if it is signal, else why it is noise.

    A slot is noise if it is a test file, is under docs/, or overlaps an earlier slot of the same
    file (the same code shown twice). Checked in that order, so a test file's reason is 'test'.
    """
    reasons: list[str] = []
    seen: list[tuple[str, int, int]] = []
    for path, start, end in spans:
        if _is_test_path(path):
            reasons.append("test")
        elif is_docs_path(path):
            reasons.append("docs")
        elif any(p == path and start <= e and s <= end for p, s, e in seen):
            reasons.append("overlap")
        else:
            reasons.append("")
        seen.append((path, start, end))
    return reasons


def noise_share(reasons: list[str]) -> float:
    return sum(1 for r in reasons if r) / len(reasons) if reasons else 0.0


# ---- building the context ----------------------------------------------------------------------


def find_checkout(question_set: OverviewSet, cache_dir: Path) -> Path:
    """The pinned checkout, which must already exist: this script never fetches."""
    dest = cache_dir / f"{question_set.name}-{question_set.commit[:12]}"
    if not (dest / ".git").exists():
        raise SystemExit(
            f"{dest} is not there. Run scripts/eval_retrieval.py once to fetch the pinned checkouts; "
            "this script makes no network call."
        )
    return dest


def build_answers(root: Path, repo_id: str, name: str, commit: str):
    """An AnswerService over an in-memory index of the checkout, built as scripts/eval_retrieval.py builds it."""
    config = load_config()
    options = index_options(config)
    embedder = build_embedder(config)
    repository = Repository(
        repo_id=repo_id,
        name=name,
        url="",
        root_path=str(root.resolve()),
        ingested_at=datetime.now(UTC),
        commit=commit,
    )
    parsed = TreeSitterAstParser().parse_repository(repository)
    retriever = FaissCodeRetriever()
    CodeIndexService(
        embedder=embedder,
        retriever=retriever,
        max_chars=options["max_chars"],
        prefix_metadata=options["prefix_metadata"],
        record_format=options["record_format"],
        window_chars=options["window_chars"],
        window_overlap=options["window_overlap"],
    ).index_repository(repository, parsed)
    settings = retrieval_settings_for(config, config.embedding_provider)
    answers = AnswerService(retriever=retriever, embedder=embedder, llm=None, settings=settings)
    return answers, config, options, settings, len(parsed.files)


def relative(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.replace("\\", "/")


def context_for(agent: RetrievalAgent, question: str, repo_id: str, root: Path) -> dict:
    """What the default path would put in front of the model for this question."""
    retrieved = agent.locate(question, repo_id, top_k=TOP_K)
    snippets = retrieved.snippets
    messages = _PROMPT.format_messages(question=question, snippets=_numbered(snippets), facts="", history="")
    prompt_chars = sum(len(str(m.content)) for m in messages)
    spans = [(relative(s.path, root), s.start_line, s.end_line) for s in snippets]
    return {"spans": spans, "prompt_chars": prompt_chars}


def score_question(question: OverviewQuestion, context: dict) -> dict:
    files = [path for path, _, _ in context["spans"]]
    reasons = noise_slots(context["spans"])
    return {
        "id": question.id,
        "topic": question.topic,
        "question": question.question,
        "slots": len(context["spans"]),
        "files": [f"{p}:{s}-{e}" for p, s, e in context["spans"]],
        "core": core_coverage(files, question.core_files),
        "noise": noise_share(reasons),
        "noise_reasons": reasons,
        "manifest": core_coverage(files, question.manifest_files) if question.manifest_files else None,
        "prompt_chars": context["prompt_chars"],
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarise(rows: list[dict]) -> dict:
    manifest = [r["manifest"] for r in rows if r["manifest"] is not None]
    return {
        "questions": len(rows),
        "core": round(mean([r["core"] for r in rows]), 4),
        "noise": round(mean([r["noise"] for r in rows]), 4),
        "manifest": round(mean(manifest), 4) if manifest else None,
        "prompt_chars": round(mean([r["prompt_chars"] for r in rows])),
    }


def run(sets: list[Path], split: str, cache_dir: Path) -> dict:
    results: dict = {"repos": {}, "split": split}
    all_rows: list[dict] = []
    for path in sets:
        question_set = load_overview_set(path)
        chosen = [q for q in question_set.questions if split == "all" or q.split == split]
        if not chosen:
            continue
        root = find_checkout(question_set, cache_dir)
        repo_id = f"overview-{question_set.name}"
        answers, config, options, settings, files = build_answers(root, repo_id, question_set.name, question_set.commit)
        agent = RetrievalAgent(answers)
        rows = [score_question(q, context_for(agent, q.question, repo_id, root)) for q in chosen]
        results["repos"][question_set.name] = {"files_indexed": files, "rows": rows, "summary": summarise(rows)}
        results["settings"] = {
            "embedding_provider": config.embedding_provider,
            "record_format": options["record_format"],
            "prefix_metadata": options["prefix_metadata"],
            "bm25": settings.bm25_enabled,
            "candidates": settings.candidates,
            "drop_stopwords": settings.drop_stopwords,
            "top_k": TOP_K,
        }
        all_rows.extend(rows)
    results["overall"] = summarise(all_rows)
    return results


def _pct(value: float | None) -> str:
    return "  -  " if value is None else f"{value:5.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=SPLITS, default="dev")
    parser.add_argument("--set", dest="sets", action="append", type=Path, help="question file (default: both)")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".codeatlas" / "eval-repos")
    args = parser.parse_args()

    result = run(args.sets or DEFAULT_SETS, args.split, args.cache_dir)
    print(f"settings: {json.dumps(result.get('settings', {}), separators=(',', ':'))}")
    print(f"split: {args.split}   (retrieval only; the live site runs other settings, see docs/RESULTS.md)")
    for name, repo in result["repos"].items():
        print(f"\n{name}: {repo['files_indexed']} files indexed")
        print(f"  {'id':<14}{'core':>6}{'noise':>7}{'manif':>7}{'chars':>7}  question")
        for row in repo["rows"]:
            print(
                f"  {row['id']:<14}{_pct(row['core'])}{_pct(row['noise'])}{_pct(row['manifest'])}"
                f"{row['prompt_chars']:>7}  {row['question']}"
            )
            for item, reason in zip(row["files"], row["noise_reasons"], strict=True):
                print(f"      {item}{'   <- ' + reason if reason else ''}")
        s = repo["summary"]
        print(f"  {'mean':<14}{_pct(s['core'])}{_pct(s['noise'])}{_pct(s['manifest'])}{s['prompt_chars']:>7}")
    o = result["overall"]
    print(
        f"\noverall ({o['questions']} questions): core {o['core']:.3f}  noise {o['noise']:.3f}  manifest {_pct(o['manifest']).strip()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
