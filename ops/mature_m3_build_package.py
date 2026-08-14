from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "mature-modernization" / "v2"
    output = root / "mature-modernization" / "jdair-cha-v2-m3.2a.tar.gz"
    required = [
        "VERSION",
        "BUILD",
        "FEATURES.env",
        "requirements.lock",
        "app/main.py",
        "app/realtime/api.py",
        "app/realtime/aee_adapter.py",
        "app/realtime/session_manager.py",
        "app/templates/m3_realtime.html",
        "app/static/realtime/realtime.js",
        "app/static/realtime/multistream_runtime.js",
        "app/static/vendor/mcs8Client.js",
        "tests/test_realtime.py",
        "tests/test_realtime_api.py",
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
            if path.is_file() and include(path):
                archive.add(
                    path,
                    arcname=path.relative_to(source),
                    recursive=False,
                )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with tarfile.open(output, "r:gz") as archive:
        names = archive.getnames()
    forbidden = [
        name
        for name in names
        if "__pycache__" in Path(name).parts
        or name.endswith((".pyc", ".pyo", ".log", ".tar.gz"))
        or Path(name).name == ".env"
        or "server-backups" in Path(name).parts
    ]
    if forbidden:
        raise SystemExit(
            "release archive contains forbidden paths: "
            + ", ".join(forbidden[:10])
        )
    result = {
        "path": str(output),
        "size": output.stat().st_size,
        "sha256": digest,
        "entries": len(names),
        "version": (source / "VERSION").read_text().strip(),
        "build": (source / "BUILD").read_text().strip(),
        "features": (source / "FEATURES.env").read_text().splitlines(),
    }
    (root / "m3-package-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
