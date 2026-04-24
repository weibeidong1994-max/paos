from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from paos.skills import SkillRegistry

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

registry = SkillRegistry()
registry.discover()


class InstallSkillRequest(BaseModel):
    repo_url: str
    name: str | None = None


class CallSkillRequest(BaseModel):
    prompt: str
    context: dict | None = None


@router.get("")
async def list_skills():
    return {"success": True, "count": len(registry.list_skills()), "skills": registry.list_skills()}


@router.get("/{name}")
async def get_skill(name: str):
    skill = registry.get(name)
    if skill is None or not skill.loaded:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"success": True, **skill.to_dict(), "instructions": skill.instructions}


@router.post("/install")
async def install_skill(request: InstallSkillRequest):
    result = registry.install_from_git(request.repo_url, request.name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Install failed"))
    return result


@router.delete("/{name}")
async def uninstall_skill(name: str):
    result = registry.uninstall(name)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Uninstall failed"))
    return result


@router.post("/{name}/call")
async def call_skill(name: str, request: CallSkillRequest):
    result = registry.call(name, request.prompt, request.context)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Skill not found"))
    return result


@router.post("/reload")
async def reload_skills():
    skills = registry.discover()
    return {"success": True, "count": len(skills), "skills": [s.to_dict() for s in skills]}
