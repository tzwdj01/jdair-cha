from __future__ import annotations

import json
import tarfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "mature-modernization" / "v2"
    output = root / "mature-modernization" / "jdair-cha-v2-m4-inspection-canary.tar.gz"
    required = [
        "VERSION",
        "BUILD",
        "FEATURES.env",
        "requirements.lock",
        "app/main.py",
        "app/config.py",
        "app/api/inspection.py",
        "app/api/inspections.py",
        "app/data/__init__.py",
        "app/data/aee_adapter.py",
        "app/data/aee_collector.py",
        "app/data/aee_http.py",
        "app/data/device_snapshot.py",
        "app/data/inspection_records.py",
        "app/data/mcs8_adapter.py",
        "app/data/mcs8_auth.py",
        "app/data/mcs8_collector.py",
        "app/data/mcs8_http.py",
        "app/data/metrics.py",
        "app/data/normalization.py",
        "app/data/pagination.py",
        "app/data/realtime_views.py",
        "app/data/store/__init__.py",
        "app/data/store/inspection_memory.py",
        "app/data/store/inspection_postgres.py",
        "app/data/store/inspection_repository.py",
        "app/data/store/memory.py",
        "app/data/store/postgres.py",
        "app/data/store/repository.py",
        "app/data/store/sinks.py",
        "app/realtime/__init__.py",
        "app/realtime/aee_adapter.py",
        "app/realtime/api.py",
        "app/realtime/errors.py",
        "app/realtime/models.py",
        "app/realtime/schemas.py",
        "app/realtime/session_manager.py",
        "app/realtime/telemetry.py",
        "app/services/business_candidates.py",
        "app/services/cache.py",
        "app/services/dashboard.py",
        "app/services/ingestion.py",
        "app/services/ingestion_scheduler.py",
        "app/services/inspection.py",
        "app/services/inspection_records.py",
        "app/services/legacy.py",
        "app/services/mcs8_scheduler.py",
        "app/services/store_factory.py",
        "app/services/trend_store.py",
        "app/templates/inspection.html",
        "app/templates/inspections.html",
        "app/templates/m2_dashboard.html",
        "app/templates/m3_realtime.html",
        "app/static/realtime/realtime.js",
        "app/static/realtime/multistream_runtime.js",
        "app/static/realtime/realtime.css",
        "app/static/vendor/mcs8Client.js",
        "migrations/0001_inspection_history.sql",
        "migrations/0002_inspection_workflow.sql",
        "migrations/README.md",
    ]
    missing = [item for item in required if not (source / item).exists()]
    if missing:
        raise SystemExit("missing source files: " + ", ".join(missing))

    def normalize_member(member: tarfile.TarInfo) -> tarfile.TarInfo:
        member.uid = 0
        member.gid = 0
        member.uname = "root"
        member.gname = "root"
        return member

    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.add(
                    path,
                    arcname=path.relative_to(source),
                    filter=normalize_member,
                )
    print(json.dumps({"package": str(output), "size": output.stat().st_size}))


if __name__ == "__main__":
    main()
