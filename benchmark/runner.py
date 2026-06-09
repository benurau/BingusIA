import asyncio
import importlib.util
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import Any

from bingus_ia.core.agent import Agent
from bingus_ia.core.types import AgentConfig


def load_tasks(tasks_dir: str) -> list[dict[str, Any]]:
    tasks = []
    tasks_path = Path(tasks_dir)
    for f in sorted(tasks_path.glob("task_*.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tasks.append(mod.TASK)
    return tasks


def evaluate_task(task: dict[str, Any], workspace: str) -> tuple[bool, str]:
    check = task["check"]
    cwd = workspace

    if check["type"] == "python_code":
        try:
            proc = subprocess.run(
                [sys.executable, "-c", check["test"]],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0:
                return True, "All assertions passed"
            else:
                stderr = (proc.stderr or "").strip()
                stdout = (proc.stdout or "").strip()
                detail = stderr if stderr else stdout
                return False, detail
        except subprocess.TimeoutExpired:
            return False, "Check timed out"
        except Exception as e:
            return False, str(e)

    elif check["type"] == "pytest":
        test_file = check["test"]
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--no-header"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return True, "All tests passed"
            else:
                stderr = (proc.stderr or "").strip()
                stdout = (proc.stdout or "").strip()
                detail = stderr if stderr else stdout
                return False, detail
        except subprocess.TimeoutExpired:
            return False, "pytest timed out"
        except Exception as e:
            return False, str(e)

    return False, f"Unknown check type: {check.get('type')}"


async def run_task(task: dict[str, Any], config: AgentConfig) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir).resolve()

        for rel_path, content in task["files"].items():
            full_path = tmp_path / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        task_config = AgentConfig(
            provider=config.provider,
            model=config.model,
            api_key=config.api_key,
            api_base_url=config.api_base_url,
            ollama_base_url=config.ollama_base_url,
            workspace_dir=str(tmp_path),
            max_turns=config.max_turns,
            memory_enabled=False,
            injection_dir="",
            prompt_dir="",
        )

        agent = Agent(task_config)
        agent_response = ""
        error = None
        try:
            agent_response = await agent.run(task["prompt"])
        except Exception as e:
            error = str(e)
        finally:
            await agent.close()

        if error:
            return {
                "id": task["id"],
                "name": task["name"],
                "passed": False,
                "detail": f"Agent error: {error}",
                "agent_response": agent_response,
            }

        passed, detail = evaluate_task(task, str(tmp_path))
        return {
            "id": task["id"],
            "name": task["name"],
            "passed": passed,
            "detail": detail,
            "agent_response": agent_response,
        }
