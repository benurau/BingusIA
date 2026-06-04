import re
from pathlib import Path
from typing import List, Optional

from bingus_ia.core.types import Injection
from bingus_ia.injections.loader import InjectionLoader


class InjectionRegistry:
    def __init__(self, injection_dir: str = "injections"):
        self.loader = InjectionLoader(injection_dir)
        self._injections: list[Injection] = []
        self._rule_stems: set[str] = set()

    @property
    def injection_dir(self) -> Path:
        return self.loader.injection_dir

    def reload(self) -> int:
        self._injections = self.loader.load_all()
        self._rule_stems = {f.stem for f in self.injection_dir.glob("rule-*.md") if f.is_file()}
        return len(self._injections)

    @property
    def injections(self) -> list[Injection]:
        return self._injections

    def match(self, user_input: str) -> list[Injection]:
        return self.loader.match(user_input, self._injections)

    def enable(self, name: str) -> bool:
        for inj in self._injections:
            if inj.name == name:
                inj.enabled = True
                return True
        return False

    def disable(self, name: str) -> bool:
        for inj in self._injections:
            if inj.name == name:
                inj.enabled = False
                return True
        return False

    def get(self, name: str) -> Optional[Injection]:
        for inj in self._injections:
            if inj.name == name:
                return inj
        return None

    def list_active(self) -> list[Injection]:
        return [i for i in self._injections if i.enabled]

    def _rule_stem_for(self, name: str) -> str:
        safe = re.sub(r"[^\w\s-]", "", name).strip()
        if not safe:
            safe = "rule"
        return f"rule-{safe.replace(' ', '-').lower()}"

    def create_rule(self, name: str, instruction: str, trigger: str = "") -> str:
        safe_name = re.sub(r"[^\w\s-]", "", name).strip()
        if not safe_name:
            safe_name = "rule"
        safe_name = safe_name.replace(" ", "-").lower()

        filename = f"rule-{safe_name}.md"
        filepath = self.injection_dir / filename

        if filepath.exists():
            existing = filepath.read_text(encoding="utf-8")
            if existing.count("---") >= 2:
                parts = existing.split("---", 2)
                front = parts[1]
                front = re.sub(r"^priority:\s*\d+", "priority: 1", front, flags=re.MULTILINE)
                front = re.sub(r"^enabled:\s*(true|false)", "enabled: true", front, flags=re.MULTILINE)
                filepath.write_text(f"---{front}---{parts[2]}\n\n# Auto-updated\n{instruction}", encoding="utf-8")
                self.reload()
                return f"Rule '{name}' updated."

        content = f"""---
name: {name}
trigger: {trigger}
priority: 1
enabled: true
urls:
---

{instruction}
"""
        filepath.write_text(content.strip() + "\n", encoding="utf-8")
        self.reload()
        return f"Rule '{name}' created."

    def delete_rule(self, name: str) -> str:
        for inj in self._injections:
            if inj.name == name or inj.name.lower() == name.lower():
                stem = self._rule_stem_for(inj.name)
                filepath = self.injection_dir / f"{stem}.md"
                if filepath.exists():
                    filepath.unlink()
                    self.reload()
                    return f"Rule '{inj.name}' deleted."
                for f in self.injection_dir.iterdir():
                    if f.stem.startswith("rule-") and inj.name.lower() in f.stem.lower():
                        f.unlink()
                        self.reload()
                        return f"Rule '{inj.name}' deleted."
        return f"Rule '{name}' not found."

    def list_rules(self) -> list[Injection]:
        return [i for i in self._injections if self._rule_stem_for(i.name) in self._rule_stems]
