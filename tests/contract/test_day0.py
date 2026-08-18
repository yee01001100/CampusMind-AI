import json
import shutil
from pathlib import Path

from scripts.check_contracts import validate_contracts
from scripts.check_day0 import validate_day0


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_contract_examples_match_shared_contract() -> None:
    assert validate_contracts(REPO_ROOT) == []


def test_day0_layout_and_configuration() -> None:
    assert validate_day0(REPO_ROOT) == []


def _copy_contract_examples(tmp_path: Path) -> Path:
    target = tmp_path / "contracts" / "examples"
    shutil.copytree(REPO_ROOT / "contracts" / "examples", target)
    return target


def test_contract_check_rejects_missing_model_field(tmp_path: Path) -> None:
    examples = _copy_contract_examples(tmp_path)
    models_path = examples / "models.valid.json"
    models = json.loads(models_path.read_text(encoding="utf-8"))
    del models["notice"]["title"]
    models_path.write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    errors = validate_contracts(tmp_path)
    assert any("notice fields differ" in error for error in errors)


def test_contract_check_rejects_naive_datetime(tmp_path: Path) -> None:
    examples = _copy_contract_examples(tmp_path)
    models_path = examples / "models.valid.json"
    models = json.loads(models_path.read_text(encoding="utf-8"))
    models["task"]["due_at"] = "2026-08-22T18:00:00"
    models_path.write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    errors = validate_contracts(tmp_path)
    assert any("task.due_at must include a timezone offset" in error for error in errors)
