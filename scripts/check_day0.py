from __future__ import annotations

import sys
import tomllib
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_contracts import validate_contracts


REQUIRED_DIRECTORIES = (
    "apps/api/agent",
    "apps/web",
    "campusmind/domain",
    "campusmind/integrations/deeptutor",
    "campusmind/repositories",
    "campusmind/services/notice",
    "campusmind/services/course",
    "campusmind/services/task",
    "campusmind/services/reminder",
    "campusmind/storage",
    "campusmind/tools",
    "data/demo",
    "data/knowledge",
    "skills/campusmind",
    "tests/agent",
    "tests/api",
    "tests/contract",
    "tests/rag",
    "tests/services",
    "tests/storage",
)

REQUIRED_FILES = (
    ".env.example",
    ".gitignore",
    "pyproject.toml",
    "requirements/README.md",
    "requirements/agent-1.txt",
    "requirements/agent-2.txt",
    "requirements/agent-3.txt",
    "scripts/check_contracts.py",
    "contracts/examples/models.valid.json",
    "contracts/examples/api.success.json",
    "contracts/examples/api.error.json",
)

FORBIDDEN_ENV_NAME_PARTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE")


def validate_day0(
    repo_root: Path | None = None, *, require_python_312: bool = True
) -> list[str]:
    root = repo_root or Path(__file__).resolve().parents[1]
    errors: list[str] = []

    if require_python_312 and sys.version_info[:2] != (3, 12):
        errors.append(
            "Day 0 checks must run with Python 3.12; "
            f"current interpreter is {sys.version_info.major}.{sys.version_info.minor}"
        )

    for relative in REQUIRED_DIRECTORIES:
        if not (root / relative).is_dir():
            errors.append(f"missing directory: {relative}")
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing file: {relative}")

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.is_file():
        with pyproject_path.open("rb") as handle:
            project = tomllib.load(handle).get("project", {})
        if project.get("requires-python") != ">=3.12,<3.13":
            errors.append("pyproject.toml must freeze Python to >=3.12,<3.13")

    env_path = root / ".env.example"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if any(part in name.upper() for part in FORBIDDEN_ENV_NAME_PARTS):
                errors.append(
                    f".env.example must not define credential variable during Day 0: {name}"
                )
            if value.lower().startswith(("sk-", "ghp_")):
                errors.append(f".env.example contains a credential-like value: {name}")

    ignore_path = root / ".gitignore"
    if ignore_path.is_file():
        ignore_text = ignore_path.read_text(encoding="utf-8")
        for required_rule in (".env", ".venv/", "*.db", "node_modules/"):
            if required_rule not in ignore_text:
                errors.append(f".gitignore is missing required rule: {required_rule}")

    errors.extend(validate_contracts(root))
    return errors


def main() -> int:
    errors = validate_day0()
    if errors:
        print("FAIL: Day 0 baseline is not ready")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: Day 0 baseline is ready on Python 3.12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
