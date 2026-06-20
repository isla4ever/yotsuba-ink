from __future__ import annotations

from collections import defaultdict, deque

from novel_workflow.workflows.schemas import WorkflowDefinition, WorkflowNode


class WorkflowCompileError(ValueError):
    """Raised when a workflow cannot be compiled into an executable graph."""


class NovelWorkflowCompiler:
    """Validate and order workflow nodes.

    The production path is intentionally shaped like LangGraph: nodes and edges
    are validated independently, then executed according to graph dependencies.
    If langgraph is installed, callers can still wrap this ordered plan in a
    StateGraph; this class keeps the core product testable without API keys.
    """

    def compile_order(self, workflow: WorkflowDefinition) -> list[WorkflowNode]:
        nodes = {node.id: node for node in workflow.nodes}
        if len(nodes) != len(workflow.nodes):
            raise WorkflowCompileError("Workflow node ids must be unique.")

        outgoing: dict[str, list[str]] = defaultdict(list)
        incoming_count: dict[str, int] = {node_id: 0 for node_id in nodes}
        for edge in workflow.edges:
            if edge.source not in nodes:
                raise WorkflowCompileError(f"Unknown edge source: {edge.source}")
            if edge.target not in nodes:
                raise WorkflowCompileError(f"Unknown edge target: {edge.target}")
            outgoing[edge.source].append(edge.target)
            incoming_count[edge.target] += 1

        queue = deque([node_id for node_id, count in incoming_count.items() if count == 0])
        ordered: list[WorkflowNode] = []
        while queue:
            node_id = queue.popleft()
            ordered.append(nodes[node_id])
            for target in outgoing[node_id]:
                incoming_count[target] -= 1
                if incoming_count[target] == 0:
                    queue.append(target)

        if len(ordered) != len(nodes):
            raise WorkflowCompileError("Workflow graph contains a cycle.")
        return ordered
