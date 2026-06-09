from pathlib import Path
from datetime import datetime
from typing import Any


def generate_report(results: list[dict[str, Any]], output_path: str | None = None) -> str:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    rate = (passed / total * 100) if total > 0 else 0

    lines = []
    lines.append("=" * 64)
    lines.append("  BingusIA Benchmark Report")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 64)
    lines.append("")

    lines.append(f"  Passed: {passed}/{total} ({rate:.1f}%)")
    lines.append("")

    lines.append("-" * 64)
    lines.append(f"  {'ID':<12} {'Status':<8} {'Task'}")
    lines.append("-" * 64)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"  {r['id']:<12} {status:<8} {r['name']}")
        if not r["passed"]:
            detail = r.get("detail", "")
            if detail:
                for line in detail.split("\n")[:5]:
                    lines.append(f"  {'':<12} {'':<8}  -> {line}")
            lines.append("")

    lines.append("-" * 64)
    lines.append(f"  Summary: {passed}/{total} passed ({rate:.1f}%)")
    lines.append("=" * 64)

    report = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report)
        print(f"Report saved to: {output_path}")

    return report


def generate_json_report(results: list[dict[str, Any]], output_path: str | None = None) -> dict:
    import json

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": round(passed / total * 100, 1) if total > 0 else 0,
        },
        "results": [
            {
                "id": r["id"],
                "name": r["name"],
                "passed": r["passed"],
                "detail": r.get("detail", "") if not r["passed"] else "",
            }
            for r in results
        ],
    }

    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2))
        print(f"JSON report saved to: {output_path}")

    return report
