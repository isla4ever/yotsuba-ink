from __future__ import annotations


class CollaborationContextError(ValueError):
    code = "context_invalid"


class CollaborationContextBudgetExceeded(CollaborationContextError):
    code = "context_budget_exceeded"

    def __init__(self, *, used_chars: int, budget_chars: int) -> None:
        super().__init__(
            f"Collaboration context uses {used_chars} characters; budget is {budget_chars}"
        )
        self.used_chars = used_chars
        self.budget_chars = budget_chars


class CollaborationSourceStale(CollaborationContextError):
    code = "collaboration_source_stale"


class CollaborationFieldNotEditable(CollaborationContextError):
    code = "collaboration_field_not_editable"


__all__ = [
    "CollaborationContextBudgetExceeded",
    "CollaborationContextError",
    "CollaborationFieldNotEditable",
    "CollaborationSourceStale",
]
