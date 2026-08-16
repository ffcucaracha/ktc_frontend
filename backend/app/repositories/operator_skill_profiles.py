from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operator_skill_profile import OperatorSkillProfile


class OperatorSkillProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_operator(self, operator_id: UUID) -> list[OperatorSkillProfile]:
        result = await self._session.execute(
            select(OperatorSkillProfile)
            .where(OperatorSkillProfile.operator_id == operator_id)
            .order_by(OperatorSkillProfile.skill_code.asc())
        )
        return list(result.scalars())

    async def replace_for_operator(
        self,
        operator_id: UUID,
        values: dict[str, tuple[float, int]],
    ) -> list[OperatorSkillProfile]:
        await self._session.execute(
            delete(OperatorSkillProfile).where(OperatorSkillProfile.operator_id == operator_id)
        )
        items = [
            OperatorSkillProfile(
                operator_id=operator_id,
                skill_code=skill_code,
                score=score,
                sample_count=sample_count,
            )
            for skill_code, (score, sample_count) in sorted(values.items())
        ]
        self._session.add_all(items)
        await self._session.flush()
        return items
