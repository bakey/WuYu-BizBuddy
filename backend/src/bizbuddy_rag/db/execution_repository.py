"""Agent 执行记录仓库."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class ExecutionRepository:
    """Agent 执行记录数据库操作."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_execution(
        self,
        agent_id: int,
        user_query: str,
        plan_json: dict[str, Any] | None = None,
    ) -> UUID:
        """创建执行记录."""
        row = self.db.execute(
            text(
                """
                INSERT INTO agent_executions (agent_id, user_query, plan_json, status)
                VALUES (:agent_id, :user_query, :plan_json, 'running')
                RETURNING id
                """
            ),
            {
                "agent_id": agent_id,
                "user_query": user_query,
                "plan_json": json.dumps(plan_json) if plan_json else "{}",
            },
        ).mappings().first()
        self.db.commit()
        return UUID(str(row["id"]))

    def create_step(
        self,
        execution_id: UUID,
        step_number: int,
        role: str,
        member_agent_id: int | None,
        action: str,
        input_json: dict[str, Any],
        status: str = "pending",
    ) -> UUID:
        """创建执行步骤."""
        row = self.db.execute(
            text(
                """
                INSERT INTO agent_execution_steps
                  (execution_id, step_number, role, member_agent_id,
                   action, input_json, status, started_at)
                VALUES
                  (:execution_id, :step_number, :role, :member_agent_id,
                   :action, :input_json, :status, now())
                RETURNING id
                """
            ),
            {
                "execution_id": execution_id,
                "step_number": step_number,
                "role": role,
                "member_agent_id": member_agent_id,
                "action": action,
                "input_json": json.dumps(input_json),
                "status": status,
            },
        ).mappings().first()
        self.db.commit()
        return UUID(str(row["id"]))

    def update_step(
        self,
        step_id: UUID,
        output_json: dict[str, Any] | None = None,
        status: str | None = None,
        review_feedback: str | None = None,
    ) -> None:
        """更新执行步骤."""
        self.db.execute(
            text(
                """
                UPDATE agent_execution_steps
                SET output_json = COALESCE(:output_json, output_json),
                    status = COALESCE(:status, status),
                    review_feedback = COALESCE(:review_feedback, review_feedback),
                    completed_at = CASE
                      WHEN :status IN ('completed', 'failed') THEN now()
                      ELSE completed_at
                    END
                WHERE id = :step_id
                """
            ),
            {
                "step_id": step_id,
                "output_json": json.dumps(output_json) if output_json is not None else None,
                "status": status,
                "review_feedback": review_feedback,
            },
        )
        self.db.commit()

    def create_review(
        self,
        execution_id: UUID,
        reviewer_agent_id: int | None,
        verdict: str,
        feedback: str,
        defects: list[str] | None = None,
    ) -> UUID:
        """创建评审记录."""
        row = self.db.execute(
            text(
                """
                INSERT INTO agent_reviews
                  (execution_id, reviewer_agent_id, verdict, feedback, defects)
                VALUES
                  (:execution_id, :reviewer_agent_id, :verdict, :feedback, :defects)
                RETURNING id
                """
            ),
            {
                "execution_id": execution_id,
                "reviewer_agent_id": reviewer_agent_id,
                "verdict": verdict,
                "feedback": feedback,
                "defects": json.dumps(defects or []),
            },
        ).mappings().first()
        self.db.commit()
        return UUID(str(row["id"]))

    def complete_execution(
        self,
        execution_id: UUID,
        status: str,
        final_answer: str,
        revision_count: int,
        plan_json: dict[str, Any] | None = None,
    ) -> None:
        """完成执行记录."""
        self.db.execute(
            text(
                """
                UPDATE agent_executions
                SET status = :status,
                    final_answer = :final_answer,
                    revision_count = :revision_count,
                    plan_json = COALESCE(:plan_json, plan_json),
                    updated_at = now()
                WHERE id = :execution_id
                """
            ),
            {
                "execution_id": execution_id,
                "status": status,
                "final_answer": final_answer,
                "revision_count": revision_count,
                "plan_json": json.dumps(plan_json) if plan_json else None,
            },
        )
        self.db.commit()

    def get_execution(self, execution_id: UUID) -> dict[str, Any] | None:
        """获取执行记录详情."""
        row = self.db.execute(
            text(
                """
                SELECT
                  e.id,
                  e.agent_id,
                  a.name AS agent_name,
                  e.user_query,
                  e.status,
                  e.final_answer,
                  e.plan_json,
                  e.revision_count,
                  e.created_at,
                  e.updated_at
                FROM agent_executions e
                JOIN agents a ON a.id = e.agent_id
                WHERE e.id = :execution_id
                """
            ),
            {"execution_id": execution_id},
        ).mappings().first()
        if row is None:
            return None
        return dict(row)

    def list_executions(
        self,
        agent_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """列出执行记录."""
        sql = """
            SELECT
              e.id,
              e.agent_id,
              a.name AS agent_name,
              e.user_query,
              e.status,
              e.revision_count,
              e.created_at,
              e.updated_at
            FROM agent_executions e
            JOIN agents a ON a.id = e.agent_id
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if agent_id is not None:
            sql += " WHERE e.agent_id = :agent_id"
            params["agent_id"] = agent_id
        sql += " ORDER BY e.created_at DESC LIMIT :limit OFFSET :offset"
        rows = self.db.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def get_execution_steps(self, execution_id: UUID) -> list[dict[str, Any]]:
        """获取执行步骤."""
        rows = self.db.execute(
            text(
                """
                SELECT
                  s.id,
                  s.execution_id,
                  s.step_number,
                  s.role,
                  s.member_agent_id,
                  a.name AS member_name,
                  s.action,
                  s.input_json,
                  s.output_json,
                  s.status,
                  s.review_feedback,
                  s.started_at,
                  s.completed_at
                FROM agent_execution_steps s
                LEFT JOIN agents a ON a.id = s.member_agent_id
                WHERE s.execution_id = :execution_id
                ORDER BY s.step_number, s.id
                """
            ),
            {"execution_id": execution_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_execution_reviews(self, execution_id: UUID) -> list[dict[str, Any]]:
        """获取评审记录."""
        rows = self.db.execute(
            text(
                """
                SELECT
                  r.id,
                  r.execution_id,
                  r.reviewer_agent_id,
                  a.name AS reviewer_name,
                  r.verdict,
                  r.feedback,
                  r.defects,
                  r.created_at
                FROM agent_reviews r
                LEFT JOIN agents a ON a.id = r.reviewer_agent_id
                WHERE r.execution_id = :execution_id
                ORDER BY r.created_at
                """
            ),
            {"execution_id": execution_id},
        ).mappings().all()
        return [dict(row) for row in rows]
