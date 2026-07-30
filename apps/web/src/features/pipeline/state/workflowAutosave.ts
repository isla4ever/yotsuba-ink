export type WorkflowAutosaveSuppressionGate<T extends object> = {
  suppress: (value: T) => void;
  shouldSuppress: (value: T) => boolean;
};

export type WorkflowAutosaveRevisionGate = {
  begin: () => number;
  invalidate: () => void;
  isCurrent: (revision: number) => boolean;
};

export function createWorkflowAutosaveSuppressionGate<T extends object>(): WorkflowAutosaveSuppressionGate<T> {
  let suppressed: T | null = null;
  return {
    suppress(value) {
      suppressed = value;
    },
    shouldSuppress(value) {
      if (value === suppressed) return true;
      suppressed = null;
      return false;
    },
  };
}

export function createWorkflowAutosaveRevisionGate(): WorkflowAutosaveRevisionGate {
  let current = 0;
  return {
    begin() {
      current += 1;
      return current;
    },
    invalidate() {
      current += 1;
    },
    isCurrent(revision) {
      return current === revision;
    },
  };
}
