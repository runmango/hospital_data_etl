from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / ".env.example", ROOT / "config.example.yaml", ROOT / "README.md"]
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?im)^(\s*[A-Z0-9_]*(?:PASSWORD|PASSWD|PWD|TOKEN|SECRET|ACCESS_KEY|PRIVATE_KEY|API_KEY)[A-Z0-9_]*\s*=\s*)(?!please_change_me|<redacted>|\$\{)([^\s#]+)"
)
SENSITIVE_YAML_RE = re.compile(
    r"(?im)^(\s*(?:password|token|secret|access_key|private_key|api_key|authorization)\s*:\s*)(?!please_change_me|<redacted>|\$\{)([^\s#]+)"
)


def sanitize_text(text: str) -> str:
    text = SENSITIVE_ASSIGNMENT_RE.sub(lambda m: m.group(1) + "please_change_me", text)
    text = SENSITIVE_YAML_RE.sub(lambda m: m.group(1) + "<redacted>", text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or sanitize example documentation files.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report files that would change.")
    mode.add_argument("--apply", action="store_true", help="Apply sanitization to example files.")
    args = parser.parse_args()

    changed = []
    for path in TARGETS:
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        sanitized = sanitize_text(original)
        if sanitized != original:
            changed.append(path.relative_to(ROOT))
            if args.apply:
                path.write_text(sanitized, encoding="utf-8")

    if changed:
        action = "Sanitized" if args.apply else "Would sanitize"
        for path in changed:
            print(f"{action}: {path}")
        return 1 if args.check else 0
    print("Example files are sanitized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
