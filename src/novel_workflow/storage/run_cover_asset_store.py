from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.storage.image_assets import inspect_image_asset
from novel_workflow.storage.run_store_support import now


class RunCoverAssetStoreMixin:
    _COVER_ASSET_ID = re.compile(r"^cover-[a-f0-9]{24}$")
    _CANDIDATE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

    def save_cover_asset(
        self,
        run_id: str,
        *,
        candidate_id: str,
        generation_key: str,
        image: GeneratedImage,
        expected_ratio: float | None = None,
    ) -> dict[str, Any]:
        if not self._CANDIDATE_ID.fullmatch(candidate_id):
            raise ValueError("封面候选 ID 不安全")
        if len(generation_key) != 64 or not all(char in "0123456789abcdef" for char in generation_key):
            raise ValueError("封面生成幂等键无效")
        info = inspect_image_asset(image.content, image.mime_type)
        if expected_ratio and abs((info.width / info.height) - expected_ratio) > 0.04:
            raise ValueError("图片比例与当前封面生成规格不一致")
        digest = hashlib.sha256(image.content).hexdigest()
        asset_id = f"cover-{digest[:24]}"
        with self._lock_for(run_id):
            index = self._read_cover_asset_index(run_id)
            existing_id = str(index["generation_keys"].get(generation_key) or "")
            if existing_id:
                existing = self._cover_asset_metadata(index, existing_id)
                if existing and self._cover_asset_file(run_id, existing).exists():
                    return existing
            relative_path = f"assets/covers/{asset_id}.{info.extension}"
            path = self.run_dir(run_id) / relative_path
            if not path.exists():
                self._write_bytes(path, image.content)
            metadata = {
                "asset_id": asset_id,
                "candidate_id": candidate_id,
                "generation_key": generation_key,
                "sha256": digest,
                "mime_type": info.mime_type,
                "width": info.width,
                "height": info.height,
                "size_bytes": len(image.content),
                "provider_asset_id": image.provider_asset_id,
                "revised_prompt": image.revised_prompt,
                "relative_path": relative_path,
                "image_url": f"/api/runs/{run_id}/cover-assets/{asset_id}",
                "created_at": now(),
            }
            index["assets"][asset_id] = metadata
            index["generation_keys"][generation_key] = asset_id
            self._write_json(self._cover_asset_index_path(run_id), index)
            return metadata

    def find_cover_asset(self, run_id: str, generation_key: str) -> dict[str, Any] | None:
        with self._lock_for(run_id):
            index = self._read_cover_asset_index(run_id)
            asset_id = str(index["generation_keys"].get(generation_key) or "")
            metadata = self._cover_asset_metadata(index, asset_id)
            if not metadata:
                return None
            path = self._cover_asset_file(run_id, metadata)
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get("sha256"):
                return None
            return metadata

    def read_cover_asset(self, run_id: str, asset_id: str) -> tuple[dict[str, Any], bytes]:
        if not self._COVER_ASSET_ID.fullmatch(asset_id):
            raise ValueError("封面资产 ID 无效")
        with self._lock_for(run_id):
            metadata = self._cover_asset_metadata(self._read_cover_asset_index(run_id), asset_id)
            if not metadata:
                raise FileNotFoundError(asset_id)
            path = self._cover_asset_file(run_id, metadata)
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != metadata.get("sha256"):
                raise ValueError("封面资产校验失败")
            inspect_image_asset(content, str(metadata.get("mime_type") or ""))
            return metadata, content

    def cleanup_cover_asset_temps(self, run_id: str) -> int:
        cover_dir = self.run_dir(run_id) / "assets" / "covers"
        if not cover_dir.exists():
            return 0
        removed = 0
        for path in cover_dir.glob(".*.tmp"):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def claim_cover_asset_retry(self, run_id: str, *, request_id: str, candidate_id: str) -> dict[str, Any]:
        if not request_id or len(request_id) > 160:
            raise ValueError("封面重试请求必须包含有效 request_id")
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            requests = data.setdefault("cover_asset_retry_requests", {})
            previous = requests.get(request_id)
            if isinstance(previous, dict):
                if previous.get("candidate_id") != candidate_id:
                    raise ValueError("同一 request_id 不能重试不同封面候选")
                return {**previous, "existing": True}
            if any(
                isinstance(item, dict) and item.get("candidate_id") == candidate_id and item.get("status") == "running"
                for item in requests.values()
            ):
                raise ValueError("该封面候选已有重试请求正在执行")
            entry = {"request_id": request_id, "candidate_id": candidate_id, "status": "running", "created_at": now()}
            requests[request_id] = entry
            self._persist(run_id, data)
            return {**entry, "existing": False}

    def finish_cover_asset_retry(self, run_id: str, *, request_id: str, status: str, event_seq: int = 0, error: str = "") -> None:
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            entry = (data.get("cover_asset_retry_requests") or {}).get(request_id)
            if not isinstance(entry, dict):
                raise ValueError("封面重试请求不存在")
            entry.update({"status": status, "event_seq": event_seq, "error": error, "finished_at": now()})
            self._persist(run_id, data)

    def _read_cover_asset_index(self, run_id: str) -> dict[str, Any]:
        path = self._cover_asset_index_path(run_id)
        if not path.exists():
            return {"version": 1, "assets": {}, "generation_keys": {}}
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "version": 1,
            "assets": data.get("assets") if isinstance(data.get("assets"), dict) else {},
            "generation_keys": data.get("generation_keys") if isinstance(data.get("generation_keys"), dict) else {},
        }

    def _cover_asset_index_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "assets" / "covers" / "index.json"

    def _cover_asset_file(self, run_id: str, metadata: dict[str, Any]) -> Path:
        relative = Path(str(metadata.get("relative_path") or ""))
        path = (self.run_dir(run_id) / relative).resolve()
        root = (self.run_dir(run_id) / "assets" / "covers").resolve()
        if root not in path.parents:
            raise ValueError("封面资产路径越界")
        return path

    @staticmethod
    def _cover_asset_metadata(index: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
        value = index.get("assets", {}).get(asset_id)
        return dict(value) if isinstance(value, dict) else None
