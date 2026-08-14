from __future__ import annotations

import hashlib
import gzip
import json
import tarfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "mature-modernization" / "v2"
    output = (
        root
        / "mature-modernization"
        / "jdair-cha-v2-m3-final-rc.tar.gz"
    )
    required = [
        "VERSION",
        "BUILD",
        "FEATURES.env",
        "requirements.lock",
        "app/main.py",
        "app/realtime/api.py",
        "app/realtime/aee_adapter.py",
        "app/realtime/session_manager.py",
        "app/realtime/telemetry.py",
        "app/templates/m3_realtime.html",
        "app/static/realtime/realtime.js",
        "app/static/realtime/multistream_runtime.js",
        "app/static/vendor/mcs8Client.js",
        "tests/test_realtime.py",
        "tests/test_realtime_api.py",
        "tests/test_realtime_ui.py",
    ]
    extras = {
        root / "docs" / "M3_REALTIME_RUNBOOK.md": (
            "docs/M3_REALTIME_RUNBOOK.md"
        ),
        root / "docs" / "M3_REALTIME_PRE_RELEASE_CHECKLIST.md": (
            "docs/M3_REALTIME_PRE_RELEASE_CHECKLIST.md"
        ),
        root / "docs" / "M3_REALTIME_RELEASE_CANDIDATE.md": (
            "docs/M3_REALTIME_RELEASE_CANDIDATE.md"
        ),
        root / "docs" / "M3_REALTIME_ARCHITECTURE.md": (
            "docs/M3_REALTIME_ARCHITECTURE.md"
        ),
        root / "docs" / "M3_FINAL_VALIDATION_REPORT.md": (
            "docs/M3_FINAL_VALIDATION_REPORT.md"
        ),
        root / "ops" / "rollback-v2.sh": "ops/rollback-v2.sh",
        root / "ops" / "mature_m3_final_release.sh": (
            "ops/mature_m3_final_release.sh"
        ),
        root / "ops" / "mature_m3_final_release_rehearsal.sh": (
            "ops/mature_m3_final_release_rehearsal.sh"
        ),
    }
    for relative in required:
        if not (source / relative).is_file():
            raise SystemExit(f"missing required release file: {relative}")
    for path in extras:
        if not path.is_file():
            raise SystemExit(f"missing required RC file: {path}")

    def include(path: Path) -> bool:
        relative = path.relative_to(source)
        return not any(
            part in {"__pycache__", "wheelhouse", ".pytest_cache"}
            for part in relative.parts
        ) and path.suffix not in {".pyc", ".pyo"}

    def normalize_member(member: tarfile.TarInfo) -> tarfile.TarInfo:
        member.uid = 0
        member.gid = 0
        member.uname = ""
        member.gname = ""
        member.mtime = 0
        member.mode = 0o755 if member.name.endswith(".sh") else 0o644
        return member

    with output.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            mtime=0,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for path in sorted(source.rglob("*")):
                    if path.is_file() and include(path):
                        archive.add(
                            path,
                            arcname=path.relative_to(source),
                            recursive=False,
                            filter=normalize_member,
                        )
                for path, arcname in extras.items():
                    archive.add(
                        path,
                        arcname=arcname,
                        recursive=False,
                        filter=normalize_member,
                    )

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    with tarfile.open(output, "r:gz") as archive:
        names = archive.getnames()
        manifest = [
            {
                "path": member.name,
                "size": member.size,
                "sha256": hashlib.sha256(
                    archive.extractfile(member).read()
                ).hexdigest(),
            }
            for member in archive.getmembers()
            if member.isfile()
        ]
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
    manifest_path = root / "m3-final-rc-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result["manifest"] = str(manifest_path)
    (root / "m3-final-rc-package-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
