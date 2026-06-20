from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "novel_workflow.api.app:app",
        host="127.0.0.1",
        port=8787,
        reload=True,
    )


if __name__ == "__main__":
    main()
