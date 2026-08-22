from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from backend.app.agent_service import SYSTEM_INSTRUCTIONS, AgentConfig
from backend.app.catalog import seed_catalog
from backend.app.database import Database
from backend.app.evaluation import (
    SINGLE_SHOT_INSTRUCTIONS,
    SINGLE_SHOT_PROMPT_VERSION,
    EvaluationCase,
    OpenAISingleShotClient,
    metrics,
    run_arm,
    run_single_shot,
    serialise_results,
)

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "backend" / "evals"
SPLIT_FILES = {
    "development": EVAL_ROOT / "development.json",
    "heldout": EVAL_ROOT / "heldout.json",
    "adversarial": EVAL_ROOT / "adversarial.json",
}


def load_cases(path: Path) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [EvaluationCase.from_dict(value) for value in payload["cases"]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible NiyamCart evaluations")
    parser.add_argument(
        "--split",
        choices=[*SPLIT_FILES, "all"],
        default="all",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run paid OpenAI single-shot and full-agent arms; requires OPENAI_API_KEY",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.live and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("--live requires OPENAI_API_KEY; no live results were fabricated")

    selected = SPLIT_FILES if args.split == "all" else {args.split: SPLIT_FILES[args.split]}
    config = AgentConfig.from_env()
    report: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "live_model_calls": args.live,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "full_agent_prompt_version": "bounded-agent-v1",
        "full_agent_instructions_sha256": __import__("hashlib").sha256(
            SYSTEM_INSTRUCTIONS.encode()
        ).hexdigest(),
        "single_shot_prompt_version": SINGLE_SHOT_PROMPT_VERSION,
        "single_shot_instructions_sha256": __import__("hashlib").sha256(
            SINGLE_SHOT_INSTRUCTIONS.encode()
        ).hexdigest(),
        "splits": {},
    }
    with tempfile.TemporaryDirectory(prefix="niyamcart-eval-") as temporary_directory:
        database = Database(f"sqlite:///{Path(temporary_directory) / 'evaluation.db'}")
        database.create_schema()
        with database.session_factory() as session:
            seed_catalog(session)
            for split, path in selected.items():
                cases = load_cases(path)
                arms: dict[str, object] = {}
                keyword_results = [run_arm(session, "keyword", case) for case in cases]
                arms["keyword"] = {
                    "metrics": metrics(keyword_results),
                    "results": serialise_results(keyword_results),
                }
                full_arm_name = "full_agent" if args.live else "full_agent_degraded"
                full_results = [run_arm(session, full_arm_name, case) for case in cases]
                arms[full_arm_name] = {
                    "metrics": metrics(full_results),
                    "results": serialise_results(full_results),
                }
                if args.live:
                    single_shot_client = OpenAISingleShotClient(config.model)
                    single_results = [
                        run_single_shot(session, case, single_shot_client) for case in cases
                    ]
                    arms["single_shot"] = {
                        "metrics": metrics(single_results),
                        "results": serialise_results(single_results),
                    }
                else:
                    arms["single_shot"] = {
                        "status": "not_run",
                        "reason": (
                            "OPENAI_API_KEY was not configured; no live result was fabricated"
                        ),
                    }
                report["splits"][split] = {"case_count": len(cases), "arms": arms}
        database.close()

    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
