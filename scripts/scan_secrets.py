from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.secret_redactor import redact_text  # noqa: E402

EXCLUDED_DIRS = {".git", ".venv", "venv", "__pycache__", "outputs", "logs", ".pytest_cache", "tests"}
SKIP_FILES = {Path("scripts/scan_secrets.py")}
SAFE_VALUES = {
    "",
    "please_change_me",
    "please_change_me_for_patient_id_hashing",
    "<redacted>",
    "实际密码",
    "实际账号",
    "str",
    "int",
    "bool",
    "None",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".env",
    ".example",
    ".gitignore",
    ".sql",
    ".sh",
}

ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|PWD|TOKEN|SECRET|ACCESS_KEY|PRIVATE_KEY|API_KEY)[A-Z0-9_]*)\s*[:=]\s*([\"']?)([^\s,;#\"']+)\2"
)
HIGH_RISK_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("authorization_bearer", re.compile(r"(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]+")),
    ("oracle_credentials", re.compile(r"(?i)\b[A-Za-z0-9_$#.-]+/[^\s/@:]+@[A-Za-z0-9_.-]+(?::\d+)?(?:/[A-Za-z0-9_$#.-]+)?")),
]


def is_safe_key(key: str) -> bool:
    normalized = key.lower()
    return normalized.endswith(("_env", "_set", "_digest")) or normalized in {"password_digest", "password_set"}


def is_safe_value(value: str) -> bool:
    stripped = value.strip().strip('"\'')
    if stripped in SAFE_VALUES:
        return True
    if stripped.startswith("${") and stripped.endswith("}"):
        return True
    if any(marker in stripped for marker in (".", "(", ")", "[", "]", "{", "}")):
        return True
    return False


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative in SKIP_FILES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"README", ".env.example"}:
            continue
        yield path


def scan_file(path: Path):
    findings = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return findings
    for line_no, line in enumerate(lines, start=1):
        for match in ASSIGNMENT_RE.finditer(line):
            key = match.group(1)
            value = match.group(3)
            if path.suffix.lower() == ".py" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
                continue
            if is_safe_key(key) or is_safe_value(value):
                continue
            findings.append((line_no, key, redact_text(line)))
        for key, pattern in HIGH_RISK_PATTERNS:
            if pattern.search(line):
                findings.append((line_no, key, redact_text(line)))
    return findings


def main() -> int:
    all_findings = []
    for path in iter_files(ROOT):
        for finding in scan_file(path):
            all_findings.append((path.relative_to(ROOT), *finding))

    for relative, line_no, key, redacted in all_findings:
        print(f"{relative}:{line_no}: {key}: {redacted}")

    if all_findings:
        print(f"Found {len(all_findings)} potential secret finding(s).", file=sys.stderr)
        return 1
    print("No potential secrets found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


