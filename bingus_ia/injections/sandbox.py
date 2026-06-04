import re
from typing import Optional

from bingus_ia.core.types import Injection


class InjectionSandbox:
    BLOCKED_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"format\s+[a-z]:",
        r">\s*/dev/sda",
        r"DROP\s+TABLE",
        r"TRUNCATE\s+TABLE",
        r"os\.system",
        r"subprocess\.call",
        r"shutil\.rmtree",
    ]

    ALLOWED_VARIABLES = {
        "workspace_dir",
        "current_file",
        "user_input",
        "model_name",
        "timestamp",
    }

    @classmethod
    def validate(cls, injection: Injection) -> tuple[bool, Optional[str]]:
        override = injection.prompt_override

        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, override, re.IGNORECASE):
                return False, f"Blocked pattern '{pattern}' found in injection '{injection.name}'"

        template_vars = re.findall(r"\{\{(\w+)\}\}", override)
        for var in template_vars:
            if var not in cls.ALLOWED_VARIABLES:
                return False, f"Disallowed template variable '{{{{{var}}}}}' in injection '{injection.name}'"

        return True, None

    @classmethod
    def render(cls, injection: Injection, context: dict) -> str:
        safe_context = {k: v for k, v in context.items() if k in cls.ALLOWED_VARIABLES}
        result = injection.prompt_override
        for key, value in safe_context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result
