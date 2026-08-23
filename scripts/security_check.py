from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "Razorpay live key": re.compile(r"\brzp_live_[A-Za-z0-9]+\b"),
    "assigned OpenAI key": re.compile(r"OPENAI_API_KEY[ \t]*=[ \t]*\S+"),
    "assigned Groq key": re.compile(r"GROQ_API_KEY[ \t]*=[ \t]*\S+"),
    "assigned Razorpay secret": re.compile(r"RAZORPAY_KEY_SECRET[ \t]*=[ \t]*\S+"),
    "assigned Twilio token": re.compile(r"TWILIO_AUTH_TOKEN[ \t]*=[ \t]*\S+"),
}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "-z"], cwd=ROOT
    ).decode(errors="strict")
    return [ROOT / name for name in output.split("\0") if name]


def main() -> None:
    findings: list[str] = []
    for path in tracked_files():
        if path.name != ".env.example" and path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(0)
                if "replace-with" in value or value.endswith("="):
                    continue
                findings.append(f"{path.relative_to(ROOT)}: possible {label}")
    active_branding = [ROOT / "app", ROOT / "components", ROOT / "lib"]
    for directory in active_branding:
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if re.search(r"kavach|saathi", path.read_text(encoding="utf-8"), re.I):
                findings.append(f"{path.relative_to(ROOT)}: legacy branding in active UI")
    if findings:
        raise SystemExit("\n".join(findings))
    print("Security and active-branding checks passed")


if __name__ == "__main__":
    main()
