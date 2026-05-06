from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

UPLOAD_TIME_RE = re.compile(r'upload-time = "([^"]+)"')


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail when uv.lock references artifacts uploaded inside the cooldown window."
    )
    parser.add_argument("--lockfile", type=Path, default=Path("uv.lock"))
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.max_age_days)
    too_new: list[tuple[int, datetime]] = []

    for line_number, line in enumerate(args.lockfile.read_text().splitlines(), start=1):
        match = UPLOAD_TIME_RE.search(line)
        if match is None:
            continue
        uploaded_at = _parse_upload_time(match.group(1))
        if uploaded_at > cutoff:
            too_new.append((line_number, uploaded_at))

    if too_new:
        print(
            f"{args.lockfile} contains artifacts uploaded less than "
            f"{args.max_age_days} days ago:"
        )
        for line_number, uploaded_at in too_new[:50]:
            print(f"  line {line_number}: {uploaded_at.isoformat()}")
        if len(too_new) > 50:
            print(f"  ... and {len(too_new) - 50} more")
        print("Refresh the lock with the repo cooldown policy or document an explicit exception.")
        return 1

    print(f"{args.lockfile} upload times satisfy the {args.max_age_days}-day cooldown.")
    return 0


def _parse_upload_time(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    if "." not in value:
        return datetime.fromisoformat(value)

    timestamp, offset = value[:-6], value[-6:]
    head, fraction = timestamp.split(".", 1)
    normalized = f"{head}.{fraction.ljust(6, '0')[:6]}{offset}"
    return datetime.fromisoformat(normalized)


if __name__ == "__main__":
    raise SystemExit(main())
