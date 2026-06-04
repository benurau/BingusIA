import os
import re
from pathlib import Path
from typing import List

from bingus_ia.core.types import Injection


class InjectionLoader:
    def __init__(self, injection_dir: str = "injections"):
        self.injection_dir = Path(injection_dir).resolve()

    def get_available(self) -> list[Path]:
        if not self.injection_dir.exists():
            return []
        return sorted(self.injection_dir.glob("*.md"))

    def load_all(self) -> list[Injection]:
        injections = []
        for filepath in self.get_available():
            try:
                injection = self._parse_file(filepath)
                if injection:
                    injections.append(injection)
            except Exception as e:
                print(f"Warning: failed to load injection {filepath}: {e}")
        injections.sort(key=lambda i: i.priority, reverse=True)
        return injections

    def _parse_file(self, filepath: Path) -> Injection | None:
        content = filepath.read_text(encoding="utf-8").strip()
        if not content:
            return None

        front_matter = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        front_matter[k.strip()] = v.strip().strip('"').strip("'")
                body = parts[2].strip()

        name = front_matter.get("name", filepath.stem)
        trigger = front_matter.get("trigger", "")
        priority = int(front_matter.get("priority", 0))
        enabled = front_matter.get("enabled", "true").lower() == "true"
        urls_raw = front_matter.get("urls", "")
        urls = [u.strip() for u in urls_raw.split(",") if u.strip()] if urls_raw else []

        return Injection(
            name=name,
            trigger_phrase=trigger,
            prompt_override=body,
            priority=priority,
            enabled=enabled,
            urls=urls,
        )

    def match(self, user_input: str, injections: list[Injection]) -> list[Injection]:
        matched = []
        for inj in injections:
            if not inj.enabled:
                continue
            if not inj.trigger_phrase:
                matched.append(inj)
            elif re.search(re.escape(inj.trigger_phrase), user_input, re.IGNORECASE):
                matched.append(inj)
        return matched
