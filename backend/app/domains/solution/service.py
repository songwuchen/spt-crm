from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import generate_uuid
from app.common.exceptions import BusinessException
from app.common.error_codes import NOT_FOUND, BUSINESS_ERROR
from app.domains.solution.models import Solution, SolutionVersion
from app.domains.solution.schemas import SolutionCreate, SolutionUpdate, SolutionVersionUpdate
from app.domains.audit.service import log_action


def _generate_solution_no() -> str:
    now = datetime.now(timezone.utc)
    import random
    seq = random.randint(1000, 9999)
    return f"SL-{now.strftime('%Y%m%d')}-{seq}"


# ==================== Solution ====================

async def list_solutions_by_project(db: AsyncSession, tenant_id: str, project_id: str):
    result = await db.execute(
        select(Solution).where(Solution.tenant_id == tenant_id, Solution.project_id == project_id)
        .order_by(Solution.created_at.desc())
    )
    return result.scalars().all()


async def get_solution(db: AsyncSession, tenant_id: str, solution_id: str) -> Solution:
    s = (await db.execute(
        select(Solution).where(Solution.id == solution_id, Solution.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not s:
        raise BusinessException(code=NOT_FOUND, message="方案不存在")
    return s


async def create_solution(db: AsyncSession, tenant_id: str, project_id: str, data: SolutionCreate, user: dict) -> dict:
    solution = Solution(
        id=generate_uuid(), tenant_id=tenant_id,
        project_id=project_id, solution_no=_generate_solution_no(),
        current_version_no=1,
        created_by_id=user["sub"], created_by_name=user.get("real_name") or user.get("username"),
        assignee_id=data.assignee_id, assignee_name=data.assignee_name,
        department_id=data.department_id, department_name=data.department_name,
    )
    db.add(solution)

    version = SolutionVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        solution_id=solution.id, version_no=1,
        title=data.title or "V1",
        summary=data.summary,
        config_json=data.config_json,
        risk_list_json=data.risk_list_json,
    )
    db.add(version)
    await db.commit()
    await db.refresh(solution)
    await db.refresh(version)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="create", resource_type="solution", resource_id=solution.id,
                     summary=f"创建方案: {solution.solution_no}")
    return {"solution": solution, "version": version}


async def update_solution(db: AsyncSession, tenant_id: str, solution_id: str, data: SolutionUpdate, user: dict) -> Solution:
    solution = await get_solution(db, tenant_id, solution_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(solution, field, val)
    await db.commit()
    await db.refresh(solution)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="solution", resource_id=solution.id,
                     summary=f"更新方案: {solution.solution_no}")
    return solution


async def delete_solution(db: AsyncSession, tenant_id: str, solution_id: str, user: dict):
    solution = await get_solution(db, tenant_id, solution_id)

    # Delete all versions
    versions = (await db.execute(
        select(SolutionVersion).where(SolutionVersion.tenant_id == tenant_id, SolutionVersion.solution_id == solution_id)
    )).scalars().all()
    for v in versions:
        await db.delete(v)

    await db.delete(solution)
    await db.commit()

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="delete", resource_type="solution", resource_id=solution_id,
                     summary=f"删除方案: {solution.solution_no}")


async def new_version(db: AsyncSession, tenant_id: str, solution_id: str, user: dict) -> SolutionVersion:
    """Create a new version by copying config_json and risk_list_json from current version."""
    solution = await get_solution(db, tenant_id, solution_id)

    current_version = (await db.execute(
        select(SolutionVersion).where(
            SolutionVersion.tenant_id == tenant_id,
            SolutionVersion.solution_id == solution_id,
            SolutionVersion.version_no == solution.current_version_no,
        )
    )).scalar_one_or_none()

    new_no = solution.current_version_no + 1
    new_ver = SolutionVersion(
        id=generate_uuid(), tenant_id=tenant_id,
        solution_id=solution_id, version_no=new_no,
        title=f"V{new_no}",
        summary=current_version.summary if current_version else None,
        config_json=current_version.config_json if current_version else None,
        risk_list_json=current_version.risk_list_json if current_version else None,
        doc_attachment_id=current_version.doc_attachment_id if current_version else None,
    )
    db.add(new_ver)

    solution.current_version_no = new_no
    await db.commit()
    await db.refresh(new_ver)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="new_version", resource_type="solution", resource_id=solution_id,
                     summary=f"创建方案新版本: {solution.solution_no} V{new_no}")
    return new_ver


# ==================== SolutionVersion ====================

async def get_versions_by_solution(db: AsyncSession, tenant_id: str, solution_id: str):
    result = await db.execute(
        select(SolutionVersion).where(
            SolutionVersion.tenant_id == tenant_id,
            SolutionVersion.solution_id == solution_id,
        ).order_by(SolutionVersion.version_no.desc())
    )
    return result.scalars().all()


async def get_version(db: AsyncSession, tenant_id: str, version_id: str) -> SolutionVersion:
    v = (await db.execute(
        select(SolutionVersion).where(SolutionVersion.id == version_id, SolutionVersion.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not v:
        raise BusinessException(code=NOT_FOUND, message="方案版本不存在")
    return v


async def update_version(db: AsyncSession, tenant_id: str, version_id: str, data: SolutionVersionUpdate, user: dict) -> SolutionVersion:
    version = await get_version(db, tenant_id, version_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(version, field, val)
    await db.commit()
    await db.refresh(version)

    await log_action(db, tenant_id=tenant_id, user_id=user["sub"], user_name=user.get("real_name") or user.get("username"),
                     action="update", resource_type="solution_version", resource_id=version_id,
                     summary=f"更新方案版本 V{version.version_no}")
    return version


async def count_solutions(db: AsyncSession, tenant_id: str) -> int:
    result = (await db.execute(
        select(func.count(Solution.id)).where(Solution.tenant_id == tenant_id)
    )).scalar() or 0
    return result
