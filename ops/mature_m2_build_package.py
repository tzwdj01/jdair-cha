from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "mature-modernization" / "v2"
    output = root / "mature-modernization" / "jdair-cha-v2-m2.tar.gz"
    required = [
        "VERSION",
        "BUILD",
        "FEATURES.env",
        "requirements.lock",
        "app/main.py",
        "app/services/dashboard.py",
        "app/templates/m2_dashboard.html",
        "tests/test_dashboard.py",
    ]
    for relative in required:
        if not (source / relative).is_file():
            raise SystemExit(f"missing required release file: {relative}")

    def include(path: Path) -> bool:
        relative = path.relative_to(source)
        return not any(
            part in {"__pycache__", "wheelhouse", ".pytest_cache"}
            for part in relative.parts
        ) and path.suffix not in {".pyc", ".pyo"}

    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            if include(path):
                archive.add(path, arcname=path.relative_to(source))

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with tarfile.open(output, "r:gz") as archive:
        names = archive.getnames()
    result = {
        "path": str(output),
        "size": output.stat().st_size,
        "sha256": digest,
        "entries": len(names),
        "version": (source / "VERSION").read_text().strip(),
        "build": (source / "BUILD").read_text().strip(),
        "features": (source / "FEATURES.env").read_text().splitlines(),
    }
    (root / "m2-package-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
