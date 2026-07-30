from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from novel_workflow.providers.stage_probe import probe_structured_stage
from novel_workflow.storage.provider_profile_store import ProviderProfileStore
from novel_workflow.storage.provider_secret_store import ProviderSecretStore
from novel_workflow.workflows.schemas import ProviderProfile


DEFAULT_RUNTIME_ROOT = Path("runtime/novel_workflow")


def main() -> None:
    args = _parse_args()
    result = asyncio.run(
        run_provider_smoke(
            runtime_root=args.runtime_root,
            provider_id=args.provider_id,
            stage_id=args.stage_id,
            max_tokens=args.max_tokens,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


async def run_provider_smoke(
    *,
    runtime_root: Path,
    provider_id: str,
    stage_id: str,
    max_tokens: int,
) -> dict[str, Any]:
    profile_store = ProviderProfileStore(runtime_root / "provider_profiles.sqlite3")
    secret_store = ProviderSecretStore(runtime_root / "provider_secrets.sqlite3")
    try:
        profile = ProviderProfile.model_validate(profile_store.read(provider_id))
    except FileNotFoundError:
        return _failure(provider_id=provider_id, stage_id=stage_id, code="provider_not_found", message=f"Provider profile not found: {provider_id}")
    api_key = secret_store.get_api_key(provider_id) or (os.environ.get(profile.api_key_env) if profile.api_key_env else "")
    if not api_key:
        return _failure(provider_id=provider_id, stage_id=stage_id, code="secret_missing", message="Provider API key is not configured in SQLite or api_key_env")
    result = await probe_structured_stage(profile, api_key=api_key, stage_id=stage_id, max_tokens=max_tokens)
    payload = result.model_dump()
    payload["api_key_source"] = "sqlite" if secret_store.has_api_key(provider_id) else "env"
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a low-token real provider smoke test against one structured Yotsuba Ink stage.")
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT, help="Runtime data root containing provider_profiles.sqlite3 and provider_secrets.sqlite3.")
    parser.add_argument("--provider-id", default="openai-compatible", help="Provider profile id to test.")
    parser.add_argument("--stage-id", default="info", choices=["info", "summary", "outline", "detail", "text"], help="Structured stage probe to run.")
    parser.add_argument("--max-tokens", type=int, default=1600, help="Low smoke-test token cap. Increase only when probing longer stages.")
    return parser.parse_args()


def _failure(*, provider_id: str, stage_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "provider_id": provider_id,
        "stage_id": stage_id,
        "stage_type": "",
        "schema_name": "",
        "error_code": code,
        "message": message,
        "errors": [],
        "summary": {},
    }


if __name__ == "__main__":
    main()
