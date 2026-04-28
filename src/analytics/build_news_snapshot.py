from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.api.news_controller import _common_meta
from src.services.news_stats_snapshot import stats_snapshot_path
from src.services.rss_digest import RssDigestClient, parse_snapshot_date


SNAPSHOT_SCHEMA_VERSION = "1.0"


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any], *, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=indent, sort_keys=False)
        tmp_file.write("\n")
        tmp_name = tmp_file.name
    os.replace(tmp_name, path)


def _unavailable_sections(derived: dict[str, Any]) -> list[str]:
    unavailable: list[str] = []
    for key, value in sorted(derived.items()):
        if isinstance(value, dict) and str(value.get("status") or "") == "unavailable":
            unavailable.append(key)
    return unavailable


def build_stats_snapshot(
    *,
    output_path: Path | None = None,
    source_url: str | None = None,
    snapshot_date: str | None = None,
    indent: int | None = 2,
) -> dict[str, Any]:
    started = time.monotonic()
    parsed_snapshot_date = parse_snapshot_date(snapshot_date)
    client = RssDigestClient(source_url=source_url) if source_url else RssDigestClient()
    bundle = client.get_payload(force_refresh=True, snapshot_date=parsed_snapshot_date)

    stats = bundle.get("stats") if isinstance(bundle.get("stats"), dict) else {}
    article_count = len(bundle.get("articles_normalized", []))
    built_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload: dict[str, Any] = {
        "status": "ok",
        "meta": {
            **_common_meta(bundle, filtered_count=article_count, returned_count=article_count),
            "stats_backend": "precomputed",
        },
        "data": {
            "derived": stats,
            "summary": bundle.get("summary", {}),
            "analysis": bundle.get("analysis", {}),
        },
        "snapshot": {
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generated_at": built_at,
            "runtime_seconds": round(time.monotonic() - started, 3),
            "input_digest_hash": _json_hash(bundle.get("upstream_payload")),
            "analysis_config": {
                "source_effect_permutations": os.getenv("RSS_SOURCE_EFFECT_PERMUTATIONS"),
                "news_data_backend": os.getenv("NEWS_DATA_BACKEND") or "json",
                "news_stats_backend": "precomputed",
            },
            "unavailable_sections": _unavailable_sections(stats),
        },
    }

    path = output_path or stats_snapshot_path()
    _atomic_write_json(path, payload, indent=indent)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the precomputed NewsLens stats snapshot.")
    parser.add_argument("--output", default=None, help="Output JSON path. Defaults to NEWS_STATS_SNAPSHOT_PATH.")
    parser.add_argument("--source-url", default=None, help="Optional RSS JSON source URL override.")
    parser.add_argument("--snapshot-date", default=None, help="Optional historical snapshot date in YYYY-MM-DD form.")
    parser.add_argument("--compact", action="store_true", help="Write compact JSON instead of pretty JSON.")
    args = parser.parse_args(argv)

    output_path = Path(args.output) if args.output else stats_snapshot_path()
    payload = build_stats_snapshot(
        output_path=output_path,
        source_url=args.source_url,
        snapshot_date=args.snapshot_date,
        indent=None if args.compact else 2,
    )
    derived = payload.get("data", {}).get("derived", {}) if isinstance(payload.get("data"), dict) else {}
    tag_sliced = derived.get("tag_sliced_analysis") if isinstance(derived, dict) else {}
    tag_summary = tag_sliced.get("summary") if isinstance(tag_sliced, dict) else {}
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output_path),
                "runtime_seconds": payload.get("snapshot", {}).get("runtime_seconds"),
                "derived_key_count": len(derived) if isinstance(derived, dict) else 0,
                "tag_sliced_summary": tag_summary if isinstance(tag_summary, dict) else {},
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
