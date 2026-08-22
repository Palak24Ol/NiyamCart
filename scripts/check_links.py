from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def main() -> None:
    names = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files", "*.md"],
        cwd=ROOT,
    ).decode().splitlines()
    broken: list[str] = []
    for name in names:
        path = ROOT / name
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for raw_target in MARKDOWN_LINK.findall(line):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or re.match(r"^(?:https?://|mailto:)", target):
                    continue
                resolved = (path.parent / target).resolve()
                if not resolved.exists():
                    broken.append(f"{name}:{line_number}: {raw_target}")
    if broken:
        raise SystemExit("Broken local Markdown links:\n" + "\n".join(broken))
    print(f"Checked local links in {len(names)} Markdown files")


if __name__ == "__main__":
    main()
