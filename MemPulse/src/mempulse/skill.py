"""PDF-defined Skill installer and runtime instructions."""

from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parent / "skill_data" / "SKILL.md"
if not SKILL_PATH.exists():
    SKILL_PATH = (
        Path(__file__).resolve().parents[2] / "skills" / "mempulse" / "SKILL.md"
    )


def install(target):
    target = Path(target).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    destination = target / "mempulse" / "SKILL.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(SKILL_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return {"installed": str(destination), "version": "0.1.0"}
