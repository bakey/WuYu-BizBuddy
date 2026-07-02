"""Agent 框架数据模型."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class SkillResult:
    """Skill 执行结果."""

    skill_name: str
    success: bool
    content: str = ""
    references: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典."""
        return {
            "skill_name": self.skill_name,
            "success": self.success,
            "content": self.content,
            "references": self.references,
            "metadata": self.metadata,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillResult":
        """从字典反序列化."""
        return cls(
            skill_name=data.get("skill_name", ""),
            success=data.get("success", False),
            content=data.get("content", ""),
            references=data.get("references", []),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
        )


@dataclass
class PlanStep:
    """执行计划中的一个步骤."""

    step_number: int
    role: str  # orchestrator / worker / reviewer
    member_agent_id: int
    action: str  # skill name or agent action
    input: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    # 运行时填充
    result: SkillResult | None = None
    status: str = "pending"  # pending / running / completed / failed
    review_feedback: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    elapsed_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典."""
        return {
            "step_number": self.step_number,
            "role": self.role,
            "member_agent_id": self.member_agent_id,
            "action": self.action,
            "input": self.input,
            "reason": self.reason,
            "result": self.result.to_dict() if self.result else None,
            "status": self.status,
            "review_feedback": self.review_feedback,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class AgentPlan:
    """Orchestrator 生成的执行计划."""

    steps: list[PlanStep]
    expected_output: str = ""
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典."""
        return {
            "steps": [step.to_dict() for step in self.steps],
            "expected_output": self.expected_output,
            "reasoning": self.reasoning,
        }


@dataclass
class ReviewResult:
    """Reviewer 评审结果."""

    verdict: str  # pass / revise
    feedback: str
    defects: list[str] = field(default_factory=list)

    @property
    def requires_revision(self) -> bool:
        """是否需要修订."""
        return self.verdict == "revise"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典."""
        return {
            "verdict": self.verdict,
            "feedback": self.feedback,
            "defects": self.defects,
        }


@dataclass
class ExecutionResult:
    """一次完整执行的最终结果."""

    execution_id: UUID
    agent_id: int
    user_query: str
    status: str
    final_answer: str
    plan: AgentPlan
    reviews: list[ReviewResult]
    revision_count: int
    references: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典."""
        return {
            "execution_id": str(self.execution_id),
            "agent_id": self.agent_id,
            "user_query": self.user_query,
            "status": self.status,
            "final_answer": self.final_answer,
            "plan": self.plan.to_dict(),
            "reviews": [r.to_dict() for r in self.reviews],
            "revision_count": self.revision_count,
            "references": self.references,
        }
