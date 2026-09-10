#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from typing import Any, Dict, List

SNAPSHOT_ID_RE = re.compile(r"com\.apple\.TimeMachine\.\d{4}-\d{2}-\d{2}-\d{6}\.local")


def run_tmutil(args: List[str]) -> tuple[int, str, str]:
    """Run tmutil and return ``(returncode, stdout, stderr)``."""
    try:
        proc = subprocess.run(["tmutil", *args], capture_output=True, text=True, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "tmutil not found on PATH"
    except OSError as exc:  # pragma: no cover - environment-specific edge case
        return 1, "", str(exc)


def snapshot_locations(volume: str) -> List[str]:
    """Return existing local-snapshot directories relevant to *volume*."""
    candidates = [
        os.path.join(volume, ".com.apple.TimeMachine.localsnapshots"),
        os.path.join(volume, ".MobileBackups"),
        os.path.join("/Volumes", "com.apple.TimeMachine.localsnapshots"),
        os.path.join("/Volumes", ".MobileBackups"),
    ]
    return [p for p in candidates if os.path.isdir(p)]


def parse_snapshot_list(stdout: str) -> List[str]:
    """Extract local snapshot IDs from tmutil output."""
    return sorted(set(SNAPSHOT_ID_RE.findall(stdout)))


def find_tmutil_status(stdout: str) -> Dict[str, Any]:
    """Extract minimal fields from ``tmutil status`` output."""
    status: Dict[str, Any] = {"running": None, "phase": None, "bytes": None}

    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Running"):
            if re.search(r"=\s*1|=\s*true", line, re.IGNORECASE):
                status["running"] = True
            elif re.search(r"=\s*0|=\s*false", line, re.IGNORECASE):
                status["running"] = False
        elif line.startswith("Phase"):
            if "=" in line:
                status["phase"] = line.split("=", 1)[1].strip().strip("; ")
        elif line.startswith("Bytes"):
            if "=" in line:
                number = re.findall(r"\d+", line)
                status["bytes"] = int(number[0]) if number else None

    return status


def list_snapshots(volume: str) -> Dict[str, Any]:
    code, out, err = run_tmutil(["listlocalsnapshots", volume])
    result: Dict[str, Any] = {"volume": volume, "snapshots": [], "error": None}
    if code != 0:
        result["error"] = err or out or "tmutil failed"
        return result

    result["snapshots"] = parse_snapshot_list(out)
    return result


def health_report(volume: str) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "volume": volume,
        "snapshot_paths": snapshot_locations(volume),
        "snapshots": [],
        "snapshot_count": 0,
        "tmutil_list_error": None,
        "tmutil_status": {"running": None, "phase": None, "bytes": None},
    }

    list_result = list_snapshots(volume)
    report["snapshots"] = list_result["snapshots"]
    report["snapshot_count"] = len(list_result["snapshots"])
    report["tmutil_list_error"] = list_result["error"]

    code, status_out, status_err = run_tmutil(["status"])
    if code == 0:
        report["tmutil_status"] = find_tmutil_status(status_out)
    else:
        report["tmutil_status_error"] = status_err or status_out

    report["recommendations"] = recommendation_lines(report)
    return report


def recommendation_lines(report: Dict[str, Any]) -> List[str]:
    recommendations: List[str] = []
    if report.get("tmutil_list_error"):
        recommendations.append("tmutil is unavailable or failed. Run the command directly: `tmutil listlocalsnapshots /`.")
        return recommendations

    count = int(report.get("snapshot_count") or 0)
    if count == 0:
        recommendations.append("No local snapshots were detected for this volume at command time.")
        return recommendations

    if report.get("tmutil_status", {}).get("running"):
        recommendations.append("Time Machine appears active. Retry after backup finishes for cleaner snapshot changes.")

    recommendations.append("List snapshot timestamps manually with: `tmutil listlocalsnapshotdates /`.")
    recommendations.append("Remove one snapshot with: `sudo tmutil deletelocalsnapshots <TIMESTAMP>`.")
    recommendations.append("Disable local snapshots temporarily in Time Machine preferences only if safe for your workflow.")

    if count > 20:
        recommendations.append("High snapshot count may indicate hidden cache growth; review backup exclusions and free-space health.")

    return recommendations


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_health(report: Dict[str, Any]) -> None:
    print(f"Volume: {report['volume']}")
    print(f"Snapshot paths visible: {', '.join(report['snapshot_paths']) or '(none)'}")
    if report["tmutil_list_error"]:
        print(f"Error: {report['tmutil_list_error']}")
    else:
        print(f"Snapshots: {report['snapshot_count']}")

    if report["tmutil_status"].get("running") is not None:
        print(f"Backup running: {report['tmutil_status']['running']}")
        if report["tmutil_status"].get("phase"):
            print(f"Phase: {report['tmutil_status']['phase']}")

    if report["recommendations"]:
        print("\nRecommendations:")
        for item in report["recommendations"]:
            print(f" - {item}")


def _print_list(result: Dict[str, Any]) -> None:
    if result["error"]:
        print(f"Error: {result['error']}")
        return

    snapshots = result["snapshots"]
    if not snapshots:
        print("No local snapshots found")
        return

    for snap in snapshots:
        print(snap)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose Time Machine local snapshots on macOS")
    parser.add_argument("--volume", default="/", help="Volume to inspect (default: /)")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("health", help="Show a full snapshot health report")
    list_parser = subparsers.add_parser("list", help="List snapshot identifiers")
    list_parser.set_defaults(command="list")

    parser.set_defaults(command="health")
    return parser


def run_report(volume: str, as_json: bool) -> int:
    report = health_report(volume)
    if as_json:
        _print_json(report)
    else:
        _print_health(report)
    return 0 if report.get("tmutil_list_error") is None else 1


def run_list(volume: str, as_json: bool) -> int:
    result = list_snapshots(volume)
    if as_json:
        _print_json(result)
    else:
        _print_list(result)

    return 0 if result["error"] is None else 1


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return run_list(args.volume, args.json)

    # default/subcommand health
    return run_report(args.volume, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
