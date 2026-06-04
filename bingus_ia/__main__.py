import asyncio
import sys
from pathlib import Path

from bingus_ia.core.agent import Agent
from bingus_ia.core.config import load_config
from bingus_ia.core.types import LLMProvider
from bingus_ia.llm.factory import create_llm_client


async def pick_ollama_model(ollama_url: str, current: str) -> str:
    client = create_llm_client(type("cfg", (), {"provider": "ollama", "ollama_base_url": ollama_url, "model": current, "api_key": "", "api_base_url": ""})())
    try:
        models = await client.list_models()
    except Exception as e:
        print(f"  Could not reach Ollama at {ollama_url}: {e}")
        return current
    finally:
        await client.close()

    if not models:
        return current

    print("  Available models:")
    names = [m.get("name", m.get("model", "")) for m in models]
    names = [n for n in names if n]
    for i, name in enumerate(names, 1):
        marker = " (default)" if name == current else ""
        print(f"    [{i}] {name}{marker}")

    while True:
        try:
            choice = input(f"  Select model [1-{len(names)}] (Enter for {current}): ").strip()
            if not choice:
                return current
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                return names[idx]
        except (ValueError, IndexError):
            pass
        print(f"  Enter a number between 1 and {len(names)}")


def pick_provider() -> str:
    providers = [p.value for p in LLMProvider]
    print("  Available providers:")
    for i, p in enumerate(providers, 1):
        print(f"    [{i}] {p}")
    while True:
        try:
            choice = input(f"  Select provider [1-{len(providers)}] (Enter for {providers[0]}): ").strip()
            if not choice:
                return providers[0]
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                return providers[idx]
        except (ValueError, IndexError):
            pass
        print(f"  Enter a number between 1 and {len(providers)}")


async def main():
    config = load_config()

    print(f"Bingus IA — Agentic Programming Assistant")
    print(f"  Provider: {config.provider}")
    if config.provider == "ollama":
        print(f"  Ollama: {config.ollama_base_url}")
    elif config.provider == "opencode":
        print(f"  OpenCode Zen: {config.api_base_url or 'https://opencode.ai/zen/v1'}")
        print(f"  API Key: {'<set>' if config.api_key else '<not set>'}")
    else:
        print(f"  API Base URL: {config.api_base_url or '(default)'}")
        print(f"  API Key: {'<set>' if config.api_key else '<not set>'}")
    print(f"  Workspace: {config.workspace_dir}")
    print(f"  Memory: {'enabled' if config.memory_enabled else 'disabled'}")
    print(f"  Max turns: {config.max_turns}")
    print()

    if len(sys.argv) == 1:
        config.provider = pick_provider()

        if config.provider == "ollama":
            url = input("  Ollama URL (Enter for http://localhost:11434): ").strip()
            if url:
                config.ollama_base_url = url
            config.model = await pick_ollama_model(config.ollama_base_url, config.model)
        else:
            if not config.api_key:
                key = input(f"  API key for {config.provider}: ").strip()
                if key:
                    config.api_key = key
            if config.provider == "openai":
                url = input("  API base URL (Enter for https://api.openai.com/v1): ").strip()
                if url:
                    config.api_base_url = url
            elif config.provider == "anthropic":
                url = input("  API base URL (Enter for https://api.anthropic.com/v1): ").strip()
                if url:
                    config.api_base_url = url
            elif config.provider == "opencode":
                url = input("  API base URL (Enter for https://opencode.ai/zen/v1): ").strip()
                if url:
                    config.api_base_url = url
                if not config.model or config.model == "codellama:7b":
                    config.model = "big-pickle"
            model = input(f"  Model name (Enter for {config.model}): ").strip()
            if model:
                config.model = model

    print(f"  Using provider: {config.provider}, model: {config.model}")
    print()

    agent = Agent(config)

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        result = await agent.run(prompt)
        print(result)
    else:
        print("Entering interactive mode. Type 'exit' to quit, '/reload' to reload injections.")
        while True:
            try:
                prompt = input(">>> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if prompt.strip().lower() in ("exit", "quit"):
                break
            if prompt.strip() == "/reload":
                count = agent.injections.reload()
                print(f"Reloaded {count} injections.")
                continue
            if prompt.strip() == "/injections":
                for inj in agent.injections.injections:
                    status = "ON" if inj.enabled else "OFF"
                    print(f"  [{status}] {inj.name} (priority={inj.priority}, trigger='{inj.trigger_phrase}')")
                continue
            if prompt.strip().startswith("/rule "):
                instruction = prompt[6:]
                words = instruction.split()
                key_words = [w for w in words if not w.startswith(('"', "'", "-", "C:", "\\", "/")) and len(w) > 2]
                name = " ".join(key_words[:6]) if key_words else instruction[:60]
                if len(name) > 60:
                    name = name[:60].rstrip()
                result = agent.injections.create_rule(name, instruction)
                print(f"  {result}")
                continue
            if prompt.strip() == "/rules":
                rules = agent.injections.list_rules()
                if not rules:
                    print("  No rules defined.")
                else:
                    for r in rules:
                        status = "ON" if r.enabled else "OFF"
                        print(f"  [{status}] {r.name}")
                continue
            if prompt.strip().startswith("/rule-delete "):
                name = prompt[13:].strip()
                result = agent.injections.delete_rule(name)
                print(f"  {result}")
                continue
            if prompt.strip() == "/workspace":
                print(f"  Workspace: {agent.config.workspace_dir}")
                continue
            if prompt.strip().startswith("/workspace "):
                path = prompt[11:].strip()
                result = agent.set_workspace(path)
                print(f"  {result.output}")
                continue
            if prompt.strip() == "/memory":
                print(agent.blocks.list_blocks().output)
                continue
            if prompt.strip().startswith("/memory "):
                rest = prompt[8:].strip()
                if "=" in rest:
                    name, _, content = rest.partition("=")
                    name = name.strip()
                    content = content.strip()
                    result = agent.blocks.set_block(name, content)
                    print(f"  {result.output}")
                else:
                    content = agent.blocks.get_block(rest)
                    if content:
                        print(f"  [{rest}]\n{content}")
                    else:
                        print(f"  Block '{rest}' not found.")
                continue

            result = await agent.run(prompt)
            print(result)
            print()

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
