import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


class SkillManifest:
    def __init__(self, name: str, description: str, version: str = "1.0.0", **kwargs: Any):
        self.name = name
        self.description = description
        self.version = version
        self.extra = kwargs

    def to_dict(self) -> dict[str, Any]:
        d = {"name": self.name, "description": self.description, "version": self.version}
        d.update(self.extra)
        return d


class Skill:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.skill_md = path / "SKILL.md"
        self.manifest: SkillManifest | None = None
        self.instructions: str = ""
        self.loaded = False

    def load(self) -> bool:
        if not self.skill_md.exists():
            logger.warning("Skill %s has no SKILL.md", self.name)
            return False
        try:
            content = self.skill_md.read_text(encoding="utf-8")
            manifest, instructions = _parse_skill_md(content)
            if manifest is None:
                logger.warning("Skill %s SKILL.md has no valid frontmatter", self.name)
                return False
            self.manifest = manifest
            self.instructions = instructions
            self.loaded = True
            return True
        except Exception as e:
            logger.error("Failed to load skill %s: %s", self.name, e)
            return False

    def to_dict(self) -> dict[str, Any]:
        if not self.loaded:
            return {"name": self.name, "status": "not_loaded"}
        return {
            "name": self.manifest.name if self.manifest else self.name,
            "description": self.manifest.description if self.manifest else "",
            "version": self.manifest.version if self.manifest else "0.0.0",
            "status": "ready",
            "path": str(self.path),
        }


class SkillRegistry:
    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._skills: dict[str, Skill] = {}

    def discover(self) -> list[Skill]:
        self._skills.clear()
        if not self.skills_dir.exists():
            return []
        for entry in sorted(self.skills_dir.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                skill = Skill(entry)
                if skill.load():
                    key = skill.manifest.name if skill.manifest else entry.name
                    self._skills[key] = skill
                    logger.info("Loaded skill: %s", key)
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._skills.values()]

    def install_from_git(self, repo_url: str, name: str | None = None) -> dict[str, Any]:
        if name is None:
            name = repo_url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
        target = self.skills_dir / name
        if target.exists():
            return {"success": False, "error": f"Skill '{name}' already exists"}
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(target)],
                check=True,
                capture_output=True,
                text=True,
            )
            skill = Skill(target)
            if not skill.load():
                shutil.rmtree(target, ignore_errors=True)
                return {"success": False, "error": "Cloned repo has no valid SKILL.md"}
            key = skill.manifest.name if skill.manifest else name
            self._skills[key] = skill
            return {"success": True, "name": key, "description": skill.manifest.description if skill.manifest else ""}
        except subprocess.CalledProcessError as e:
            shutil.rmtree(target, ignore_errors=True)
            return {"success": False, "error": f"git clone failed: {e.stderr}"}
        except Exception as e:
            shutil.rmtree(target, ignore_errors=True)
            return {"success": False, "error": str(e)}

    def uninstall(self, name: str) -> dict[str, Any]:
        skill = self._skills.get(name)
        if skill is None:
            for key, s in self._skills.items():
                if s.path.name == name:
                    skill = s
                    name = key
                    break
        if skill is None:
            return {"success": False, "error": f"Skill '{name}' not found"}
        try:
            shutil.rmtree(skill.path, ignore_errors=True)
            self._skills.pop(name, None)
            return {"success": True, "name": name}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def call(self, name: str, prompt: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        skill = self._skills.get(name)
        if skill is None or not skill.loaded:
            return {"success": False, "error": f"Skill '{name}' not found or not loaded"}
        return {
            "success": True,
            "skill": name,
            "instructions": skill.instructions,
            "prompt": prompt,
            "context": context or {},
        }


def _parse_skill_md(content: str) -> tuple[SkillManifest | None, str]:
    if not content.startswith("---"):
        return None, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content
    try:
        frontmatter = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, content
    if not isinstance(frontmatter, dict) or "name" not in frontmatter or "description" not in frontmatter:
        return None, content
    name = frontmatter.pop("name")
    description = frontmatter.pop("description")
    version = frontmatter.pop("version", "1.0.0")
    manifest = SkillManifest(name=name, description=description, version=version, **frontmatter)
    instructions = parts[2].strip()
    return manifest, instructions
