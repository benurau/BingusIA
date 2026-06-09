"""
BingusIA Benchmark Suite

Usage:
    python benchmark/run.py [--provider ollama] [--model codellama:7b] [--tasks 1,2,3] [--output report.txt]

Examples:
    python benchmark/run.py
    python benchmark/run.py --provider openai --model gpt-4 --tasks 1-10
    python benchmark/run.py --provider anthropic --model claude-3-opus-20240229 --max-turns 50
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bingus_ia.core.types import AgentConfig
from benchmark.runner import load_tasks, run_task
from benchmark.report import generate_report, generate_json_report


def parse_task_spec(spec: str) -> set[int]:
    selected = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            selected.update(range(int(start), int(end) + 1))
        else:
            selected.add(int(part))
    return selected


async def main():
    parser = argparse.ArgumentParser(description="BingusIA Benchmark Suite")
    parser.add_argument("--provider", default="ollama", help="LLM provider (ollama, openai, anthropic, opencode)")
    parser.add_argument("--model", default="", help="Model name (default from config)")
    parser.add_argument("--api-key", default="", help="API key for cloud providers")
    parser.add_argument("--api-base-url", default="", help="Custom API base URL")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--max-turns", type=int, default=50, help="Max agent turns per task")
    parser.add_argument("--tasks", default="", help="Task numbers to run, e.g. '1,2,3' or '1-10'")
    parser.add_argument("--output", default="", help="Save report to file")
    parser.add_argument("--json", default="", help="Save JSON report to file")
    parser.add_argument("--tasks-dir", default=str(Path(__file__).resolve().parent / "tasks"), help="Tasks directory")
    args = parser.parse_args()

    config = AgentConfig(
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        api_base_url=args.api_base_url,
        ollama_base_url=args.ollama_url,
        max_turns=args.max_turns,
        memory_enabled=False,
        injection_dir="",
        prompt_dir="",
    )

    all_tasks = load_tasks(args.tasks_dir)

    if args.tasks:
        selected_ids = parse_task_spec(args.tasks)
        tasks = [t for t in all_tasks if int(t["id"].split("_")[1]) in selected_ids]
    else:
        tasks = all_tasks

    if not tasks:
        print("No tasks found.")
        return

    print(f"\n  BingusIA Benchmark — {len(tasks)} task(s)")
    print(f"  Provider: {args.provider}  Model: {config.model or '(from config)'}")
    print(f"  Max turns per task: {args.max_turns}")
    print()

    results = []
    for i, task in enumerate(tasks, 1):
        label = f"[{i}/{len(tasks)}] {task['id']} — {task['name']}"
        print(f"  {label}", end="", flush=True)

        start = time.time()
        result = await run_task(task, config)
        elapsed = time.time() - start

        status = "PASS" if result["passed"] else "FAIL"
        print(f"  {status}  ({elapsed:.1f}s)")

        results.append(result)

    print()
    report = generate_report(results, args.output)
    print(report)

    if args.json:
        generate_json_report(results, args.json)


if __name__ == "__main__":
    asyncio.run(main())
