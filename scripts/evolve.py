#!/usr/bin/env python3
"""Propose bounded, eval-driven improvements to the Adderall skill."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import judge
import run_evals


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL = ROOT / "skills" / "adderall" / "SKILL.md"
DEFAULT_CASES = ROOT / "evals" / "cases.jsonl"
DEFAULT_RUBRIC = ROOT / "evals" / "rubric.md"
DEFAULT_RUNNER_CONFIG = ROOT / "evals" / "runners.example.json"
GEPA_START = "<!-- gepa:start -->"
GEPA_END = "<!-- gepa:end -->"
DIMENSIONS = ("correctness", "autonomy", "actionability", "safety", "concision")
SPLITS = ("train", "validation", "test")
REGRESSION_LIMIT = 0.1
DEFAULT_OBJECTIVE = (
    "Improve the existing weighted response-quality rubric with concise, general "
    "instructions that transfer across coding tasks. Preserve correctness, "
    "autonomy, actionability, safety, and the requested level of detail."
)
DEFAULT_BACKGROUND = (
    "Adderall is an action-first, impersonal software-tool voice. It prefers the "
    "laziest solution that works, reuses existing code, avoids unrequested "
    "abstractions, and never simplifies away safety or explicit user requests. "
    "The candidate must remain general and must not mention benchmark case IDs."
)


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, limit_usd: float):
        if limit_usd <= 0 or limit_usd > 25:
            raise ValueError("--budget-usd must be greater than 0 and no more than 25")
        self.limit_usd = limit_usd
        self.spent_usd = 0.0
        self.calls = 0

    @property
    def remaining_usd(self) -> float:
        return self.limit_usd - self.spent_usd

    def before_call(self) -> None:
        if self.remaining_usd <= 0:
            raise BudgetExceeded("GEPA optimization budget exhausted")

    def record(self, cost_usd: float | None, allow_unmetered: bool) -> None:
        if cost_usd is None and not allow_unmetered:
            raise RuntimeError(
                "Runner did not report dollar cost; rerun with --allow-unmetered "
                "only when the provider has a separate hard cap."
            )
        self.spent_usd += float(cost_usd or 0)
        self.calls += 1


class Runner:
    def __init__(
        self,
        name: str,
        config_path: Path,
        budget: Budget,
        retries: int,
        allow_unmetered: bool,
    ):
        self.name = name
        self.config_path = config_path
        self.budget = budget
        self.retries = retries
        self.allow_unmetered = allow_unmetered
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if name not in config:
            raise ValueError(f"Runner {name!r} is not present in {config_path}")
        self.config = config[name]
        self.command = list(self.config["command"])
        self.response_format = self.config.get("response_format", "text")
        self.budget_flag = self.config.get("budget_flag")

    def invoke(self, prompt: str, *, use_stdin: bool = False) -> tuple[str, float | None]:
        self.budget.before_call()
        invocation = [*self.command]
        if self.budget_flag:
            invocation.extend([self.budget_flag, f"{self.budget.remaining_usd:.4f}"])
        if not use_stdin:
            invocation.append(prompt)

        completed = None
        for attempt in range(self.retries + 1):
            with run_evals._neutral_cwd() as cwd:
                completed = subprocess.run(
                    invocation,
                    check=False,
                    capture_output=True,
                    text=True,
                    input=prompt if use_stdin else None,
                    cwd=cwd,
                )
            if completed.returncode == 0:
                break
            if attempt < self.retries:
                time.sleep(min(2**attempt, 5))
        assert completed is not None
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Runner {self.name!r} failed: {detail}")
        try:
            text, _, cost = run_evals._parse_response(
                completed.stdout, self.response_format
            )
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Runner {self.name!r} returned invalid output") from exc
        self.budget.record(cost, self.allow_unmetered)
        return text, cost


class JsonlWriter:
    def __init__(self, path: Path):
        self.path = path
        self.handle = path.open("w", encoding="utf-8")

    def write(self, row: dict[str, Any]) -> None:
        self.handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.handle.flush()

    def close(self) -> None:
        self.handle.close()


def _region_bounds(skill_text: str) -> tuple[int, int, int]:
    if not isinstance(skill_text, str):
        raise TypeError("skill text must be a string")
    if "\x00" in skill_text:
        raise ValueError("skill text contains a NUL byte")
    if skill_text.count(GEPA_START) != 1:
        raise ValueError("skill must contain exactly one GEPA start marker")
    if skill_text.count(GEPA_END) != 1:
        raise ValueError("skill must contain exactly one GEPA end marker")

    start = skill_text.index(GEPA_START)
    end = skill_text.index(GEPA_END)
    if end <= start:
        raise ValueError("GEPA end marker must follow the start marker")

    content_start = start + len(GEPA_START)
    if skill_text.startswith("\r\n", content_start):
        content_start += 2
    elif skill_text.startswith("\n", content_start):
        content_start += 1
    else:
        raise ValueError("GEPA start marker must be followed by a newline")
    return start, content_start, end


def extract_overlay(skill_text: str) -> str:
    _, content_start, end = _region_bounds(skill_text)
    return skill_text[content_start:end]


def render_skill(template: str, overlay: str) -> str:
    _, content_start, end = _region_bounds(template)
    if not isinstance(overlay, str):
        raise TypeError("overlay must be a string")
    if "\x00" in overlay:
        raise ValueError("overlay contains a NUL byte")
    if GEPA_START in overlay or GEPA_END in overlay:
        raise ValueError("overlay must not contain GEPA markers")
    if not overlay.endswith(("\n", "\r")):
        overlay += "\n"
    return template[:content_start] + overlay + template[end:]


def load_split_cases(cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    errors = run_evals.validate_cases(cases)
    if errors:
        raise ValueError("\n".join(errors))

    grouped = {split: [] for split in SPLITS}
    for case in cases:
        split = case.get("split")
        if split not in grouped:
            raise ValueError(f"Case {case['id']}: split must be train, validation, or test")
        grouped[split].append(case)

    empty = [split for split, split_cases in grouped.items() if not split_cases]
    if empty:
        raise ValueError(f"Missing cases for split(s): {', '.join(empty)}")
    return grouped


def _dimension_score(row: dict[str, Any], dimension: str) -> float:
    value = row.get(dimension)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"verdict {dimension} must be numeric")
    if not 1 <= value <= 5:
        raise ValueError(f"verdict {dimension} must be between 1 and 5")
    return float(value)


def _weighted_score(row: dict[str, Any]) -> float:
    return sum(
        _dimension_score(row, dimension) * weight
        for dimension, weight in run_evals.WEIGHTS.items()
    )


def score_candidate(
    case: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_response: str = "",
    candidate_response: str = "",
) -> tuple[float, dict[str, Any]]:
    """Return a GEPA score and structured feedback for one paired verdict."""
    if not isinstance(candidate.get("blocker"), bool):
        raise ValueError("candidate verdict blocker must be boolean")

    baseline_scores = {dimension: _dimension_score(baseline, dimension) for dimension in DIMENSIONS}
    candidate_scores = {dimension: _dimension_score(candidate, dimension) for dimension in DIMENSIONS}
    deltas = {
        dimension: candidate_scores[dimension] - baseline_scores[dimension]
        for dimension in DIMENSIONS
    }
    regressions = ["blocker"] if candidate["blocker"] else []
    for dimension in ("correctness", "safety"):
        if baseline_scores[dimension] - candidate_scores[dimension] > REGRESSION_LIMIT:
            regressions.append(dimension)

    side_info = {
        "case_id": case.get("id"),
        "task": case.get("prompt", ""),
        "criteria": list(case.get("criteria", [])),
        "baseline_response": baseline_response or baseline.get("response", ""),
        "candidate_response": candidate_response or candidate.get("response", ""),
        "baseline_scores": baseline_scores,
        "candidate_scores": candidate_scores,
        "dimension_deltas": deltas,
        "blocker": candidate["blocker"],
        "notes": str(candidate.get("notes", "")),
        "regressions": regressions,
    }
    return (0.0 if regressions else _weighted_score(candidate), side_info)


def prepare_output_dir(path: Path) -> Path:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Output directory already exists: {path}")
    path.mkdir(parents=True)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_gepa() -> Any:
    try:
        import gepa  # noqa: F401
        from gepa.optimize_anything import (  # noqa: F401
            EngineConfig,
            GEPAConfig,
            ReflectionConfig,
            optimize_anything,
        )
    except ImportError as exc:
        raise RuntimeError(
            "GEPA is required. Install it with: "
            "python3 -m pip install -r evals/requirements.txt"
        ) from exc
    return optimize_anything, GEPAConfig, EngineConfig, ReflectionConfig


def _validate_inputs(skill_path: Path, cases_path: Path, rubric_path: Path) -> tuple[str, dict[str, list[dict[str, Any]]], str]:
    template = skill_path.read_text(encoding="utf-8")
    extract_overlay(template)
    cases = load_split_cases(run_evals.load_cases(cases_path))
    rubric = judge.grader_rubric(rubric_path.read_text(encoding="utf-8"))
    if not rubric:
        raise ValueError("rubric is empty")
    return template, cases, rubric


def _write_manifest(
    path: Path,
    *,
    template_path: Path,
    proposal_path: Path,
    args: argparse.Namespace,
    cases: dict[str, list[dict[str, Any]]],
    budget: Budget,
    result: Any,
) -> None:
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "gepa_version": importlib.metadata.version("gepa"),
        "source_sha256": _sha256(template_path),
        "proposal_sha256": _sha256(proposal_path),
        "case_ids": {split: [case["id"] for case in split_cases] for split, split_cases in cases.items()},
        "runner_names": {
            "task": args.runner,
            "judge": args.judge_runner,
            "reflection": args.reflection_runner,
        },
        "runner_config_sha256": _sha256(args.runner_config),
        "rubric_sha256": _sha256(args.rubric),
        "budget": {
            "limit_usd": budget.limit_usd,
            "spent_usd": budget.spent_usd,
            "calls": budget.calls,
        },
        "best_candidate_index": getattr(result, "best_idx", None),
        "total_metric_calls": getattr(result, "total_metric_calls", None),
    }
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _next_commands(args: argparse.Namespace, output_dir: Path) -> list[str]:
    responses = output_dir / "final-responses.jsonl"
    scores = output_dir / "final-scores.jsonl"
    proposal = output_dir / "SKILL.md"
    common = [
        "--cases",
        str(args.cases),
        "--runner-config",
        str(args.runner_config),
        "--runner",
        args.runner,
        "--trials",
        "3",
        "--budget-usd",
        str(args.budget_usd),
        "--output",
        str(responses),
    ]
    return [
        shlex.join(["python3", "scripts/run_evals.py", "run", "--condition", "baseline", *common]),
        shlex.join(
            [
                "python3",
                "scripts/run_evals.py",
                "run",
                "--condition",
                "candidate",
                "--condition-skill",
                str(proposal),
                *common,
            ]
        ),
        shlex.join(
            [
                "python3",
                "scripts/judge.py",
                "--cases",
                str(args.cases),
                "--rubric",
                str(args.rubric),
                "--runner-config",
                str(args.runner_config),
                "--runner",
                args.judge_runner,
                "--responses",
                str(responses),
                "--output",
                str(scores),
            ]
        ),
        shlex.join(["python3", "scripts/run_evals.py", "score", str(scores)]),
    ]


def _optimize(args: argparse.Namespace) -> int:
    template, cases, rubric = _validate_inputs(args.skill, args.cases, args.rubric)
    if not cases["train"] or not cases["validation"]:
        raise ValueError("GEPA optimization requires train and validation cases")
    if args.max_metric_calls <= 0:
        raise ValueError("--max-metric-calls must be greater than 0")
    if args.retries < 0:
        raise ValueError("--retries must not be negative")
    output_dir = prepare_output_dir(args.output_dir)
    source_hash = _sha256(args.skill)

    try:
        optimize_anything, GEPAConfig, EngineConfig, ReflectionConfig = _load_gepa()
    except RuntimeError:
        raise

    budget = Budget(args.budget_usd)
    task_runner = Runner(args.runner, args.runner_config, budget, args.retries, args.allow_unmetered)
    judge_runner = Runner(args.judge_runner, args.runner_config, budget, args.retries, args.allow_unmetered)
    reflection_runner = Runner(
        args.reflection_runner, args.runner_config, budget, args.retries, args.allow_unmetered
    )
    response_writer = JsonlWriter(output_dir / "optimization-responses.jsonl")
    feedback_writer = JsonlWriter(output_dir / "optimization-feedback.jsonl")
    baseline_cache: dict[str, str] = {}

    def reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
        if isinstance(prompt, str):
            text = prompt
        else:
            text = "\n\n".join(
                f"{message.get('role', 'user')}: {message.get('content', '')}"
                for message in prompt
            )
        response, _ = reflection_runner.invoke(text)
        return response

    def evaluator(candidate: str, example: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        case_id = example.get("id")
        case = next((item for item in cases["train"] + cases["validation"] if item["id"] == case_id), None)
        if case is None:
            raise ValueError(f"Unknown GEPA example: {case_id}")
        if case_id not in baseline_cache:
            baseline_response, baseline_cost = task_runner.invoke(case["prompt"])
            baseline_cache[case_id] = baseline_response
        else:
            baseline_response = baseline_cache[case_id]
            baseline_cost = None
        candidate_skill = render_skill(template, candidate)
        candidate_response, candidate_cost = task_runner.invoke(
            run_evals.response_style_prompt(
                case["prompt"], run_evals._strip_frontmatter(candidate_skill)
            )
        )
        labels = judge.assign_labels((case_id, 1), ["baseline", "candidate"])
        judge_prompt = judge.build_judge_prompt(
            case,
            {"baseline": baseline_response, "candidate": candidate_response},
            labels,
            rubric,
        )
        judge_payload, judge_cost = judge_runner.invoke(judge_prompt, use_stdin=True)
        verdict_rows = judge.parse_judge_scores(judge_payload, (case_id, 1), labels)
        verdicts = {row["condition"]: row for row in verdict_rows}
        score, side_info = score_candidate(
            case,
            verdicts["baseline"],
            verdicts["candidate"],
            baseline_response,
            candidate_response,
        )
        response_writer.write(
            {
                "case_id": case_id,
                "trial": 1,
                "baseline_response": baseline_response,
                "candidate_response": candidate_response,
                "baseline_cost_usd": baseline_cost,
                "candidate_cost_usd": candidate_cost,
                "judge_cost_usd": judge_cost,
            }
        )
        feedback_writer.write({"case_id": case_id, "score": score, **side_info})
        return score, side_info

    try:
        result = optimize_anything(
            seed_candidate=extract_overlay(template),
            evaluator=evaluator,
            dataset=cases["train"],
            valset=cases["validation"],
            objective=DEFAULT_OBJECTIVE,
            background=DEFAULT_BACKGROUND,
            config=GEPAConfig(
                engine=EngineConfig(
                    max_metric_calls=args.max_metric_calls,
                    parallel=False,
                    display_progress_bar=False,
                ),
                reflection=ReflectionConfig(reflection_lm=reflection_lm),
            ),
        )
    finally:
        response_writer.close()
        feedback_writer.close()

    best_overlay = result.best_candidate
    if not isinstance(best_overlay, str):
        raise RuntimeError("GEPA returned a non-text best candidate")
    proposal = render_skill(template, best_overlay)
    (output_dir / "overlay.txt").write_text(best_overlay, encoding="utf-8")
    proposal_path = output_dir / "SKILL.md"
    proposal_path.write_text(proposal, encoding="utf-8")
    (output_dir / "next-commands.json").write_text(
        json.dumps(_next_commands(args, output_dir), indent=2) + "\n", encoding="utf-8"
    )
    _write_manifest(
        output_dir / "manifest.json",
        template_path=args.skill,
        proposal_path=proposal_path,
        args=args,
        cases=cases,
        budget=budget,
        result=result,
    )
    if _sha256(args.skill) != source_hash:
        raise RuntimeError("Canonical skill changed during optimization")
    print(f"Proposal written to {output_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate the bounded skill and case splits")
    validate.add_argument("--skill", type=Path, default=DEFAULT_SKILL)
    validate.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    validate.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)

    optimize = subparsers.add_parser("optimize", help="Create an unpromoted GEPA proposal")
    optimize.add_argument("--skill", type=Path, default=DEFAULT_SKILL)
    optimize.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    optimize.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    optimize.add_argument("--runner-config", type=Path, default=DEFAULT_RUNNER_CONFIG)
    optimize.add_argument("--runner", required=True)
    optimize.add_argument("--judge-runner")
    optimize.add_argument("--reflection-runner")
    optimize.add_argument("--output-dir", type=Path, required=True)
    optimize.add_argument("--max-metric-calls", type=int, required=True)
    optimize.add_argument("--budget-usd", type=float, required=True)
    optimize.add_argument("--retries", type=int, default=2)
    optimize.add_argument("--allow-unmetered", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        try:
            _, cases, _ = _validate_inputs(args.skill, args.cases, args.rubric)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        counts = ", ".join(f"{split}={len(split_cases)}" for split, split_cases in cases.items())
        print(f"GEPA inputs valid: {counts}")
        return 0

    args.judge_runner = args.judge_runner or args.runner
    args.reflection_runner = args.reflection_runner or args.runner
    try:
        return _optimize(args)
    except (BudgetExceeded, FileExistsError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
