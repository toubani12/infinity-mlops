from typing import Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator


class InvalidCommand(ValueError):
    pass


class AgentCommand(BaseModel):
    """agent.commands v1: a human decision on a run waiting for approval."""

    run_id: str
    command_id: str
    timestamp: str
    action: Literal["approve", "reject"]
    actor: str = Field(min_length=1)
    reason: str | None = None

    @model_validator(mode="after")
    def reject_needs_a_reason(self) -> Self:
        if self.action == "reject" and len(self.reason or "") < 3:
            raise ValueError("a reject command needs a reason of at least 3 characters")
        return self

    @classmethod
    def parse(cls, message: dict) -> "AgentCommand":
        try:
            return cls.model_validate(message)
        except ValidationError as exc:
            raise InvalidCommand(str(exc)) from exc

    def resume_value(self) -> dict:
        return {
            "action": self.action,
            "actor": self.actor,
            "reason": self.reason,
            "command_id": self.command_id,
        }
