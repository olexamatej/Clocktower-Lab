"""Portable Markdown personas; template assignment always makes a private copy."""

import re
import uuid
from pathlib import Path

SECTIONS = ("Communication", "Decisions", "Uncertainty", "Trust", "Bluffing", "Role adaptation")
BUILTINS = Path(__file__).parent / "personas"


def validate_persona(text: str) -> str:
    if not 100 <= len(text) <= 20000:
        raise ValueError("Persona must contain 100–20000 characters")
    match = re.search(r"^# (\S[^\n]*)$", text, re.MULTILINE)
    if not match:
        raise ValueError("Persona needs a # Name heading")
    for section in SECTIONS:
        if not re.search(rf"^## {section}\s*\n\S", text, re.MULTILINE):
            raise ValueError(f"Persona needs a substantive ## {section} section")
    return match[1]


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != ".md":
        raise ValueError("Persona must be a .md file inside the persona directory")
    return path


class PersonaStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def read(self, ref: str) -> str:
        if ref.startswith("builtin:"):
            path = safe_path(BUILTINS, ref[8:] + ".md")
        else:
            path = safe_path(self.root, ref)
        text = path.read_text(encoding="utf-8")
        validate_persona(text)
        return text

    def save(self, text: str, ref: str | None = None) -> str:
        validate_persona(text)
        ref = ref or f"custom/{uuid.uuid4().hex}.md"
        path = safe_path(self.root, ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)
        return ref

    def copy(self, ref: str) -> str:
        return self.save(self.read(ref), f"players/{uuid.uuid4().hex}.md")

    def list(self) -> list[dict]:
        result = []
        for path in sorted(BUILTINS.glob("*.md")):
            result.append(
                {"ref": f"builtin:{path.stem}", "name": validate_persona(path.read_text()), "builtin": True}
            )
        for path in sorted(self.root.rglob("*.md")):
            try:
                result.append(
                    {
                        "ref": str(path.relative_to(self.root)),
                        "name": validate_persona(path.read_text()),
                        "builtin": False,
                    }
                )
            except ValueError:
                continue
        return result
