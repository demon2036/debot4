from pathlib import Path


def test_every_active_python_file_is_at_most_300_lines() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = list((root / "src").rglob("*.py")) + list((root / "tests").rglob("*.py"))
    oversized = {
        str(path.relative_to(root)): len(path.read_text(encoding="utf-8").splitlines())
        for path in targets
        if len(path.read_text(encoding="utf-8").splitlines()) > 300
    }
    assert not oversized, oversized
