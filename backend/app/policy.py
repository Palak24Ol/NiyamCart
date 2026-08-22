import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "policy.json"


class PolicyEvaluationRequest(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    total_paise: int = Field(default=0, ge=0)
    line_count: int = Field(default=0, ge=0)
    max_line_quantity: int = Field(default=0, ge=0)


class PolicyDecision(BaseModel):
    decision: Literal["allow", "deny", "escalate"]
    rule_id: str
    explanation: str
    policy_version: str


@lru_cache(maxsize=1)
def load_policy() -> dict[str, object]:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Merchant policy must be an object")
    return payload


def _matches(condition: dict[str, object], values: dict[str, object]) -> bool:
    operator = condition["operator"]
    if operator == "always":
        return True
    actual = values.get(str(condition["field"]))
    expected = condition["value"]
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    if operator == "not_equal":
        return actual != expected
    if operator == "greater_than":
        return isinstance(actual, int) and isinstance(expected, int) and actual > expected
    raise ValueError(f"Unsupported policy operator: {operator}")


def evaluate_policy(request: PolicyEvaluationRequest) -> PolicyDecision:
    policy = load_policy()
    values = request.model_dump()
    for rule in policy["rules"]:
        if _matches(rule["condition"], values):
            return PolicyDecision(
                decision=rule["decision"],
                rule_id=rule["id"],
                explanation=rule["description"],
                policy_version=policy["policy_version"],
            )
    raise RuntimeError("Policy has no terminal rule")
