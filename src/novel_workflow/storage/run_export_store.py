from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import zipfile
from typing import Any


class RunExportStoreMixin:
    _EXPORT_FORMATS = {"md", "json", "zip"}

    def list_exports(self, run_id: str) -> list[dict[str, Any]]:
        data = self.read(run_id)
        return list(reversed([copy.deepcopy(item) for item in data.get("exports") or []]))

    def read_export(self, run_id: str, export_id: str) -> tuple[dict[str, Any], bytes]:
        self._validate_export_id(export_id)
        receipt = next((item for item in self.read(run_id).get("exports") or [] if item.get("export_id") == export_id), None)
        if not receipt:
            raise FileNotFoundError(export_id)
        package_format = self._validate_export_format(str(receipt.get("format") or ""))
        path = self.run_dir(run_id) / "exports" / f"{export_id}.{package_format}"
        if not path.exists():
            raise FileNotFoundError(export_id)
        content = path.read_bytes()
        if int(receipt.get("schema_version") or 0) >= 1:
            self._validate_receipt_content(receipt, content)
        else:
            self._validate_legacy_receipt_content(receipt, content)
        return copy.deepcopy(receipt), content

    def find_export_request(self, run_id: str, request_id: str) -> tuple[dict[str, Any], str] | None:
        data = self.read(run_id)
        alias = (data.get("export_requests") or {}).get(request_id)
        if isinstance(alias, dict):
            receipt = self._receipt_by_id(data, str(alias.get("export_id") or ""))
            if receipt:
                return copy.deepcopy(receipt), str(alias.get("request_digest") or "")
        receipt = next((item for item in data.get("exports") or [] if item.get("request_id") == request_id), None)
        if not isinstance(receipt, dict):
            return None
        return copy.deepcopy(receipt), str(receipt.get("request_digest") or "")

    def save_export(
        self,
        run_id: str,
        receipt: dict[str, Any],
        content: bytes,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        export_id = str(receipt.get("export_id") or "")
        request_id = str(receipt.get("request_id") or "")
        if not export_id or not request_id:
            raise ValueError("导出收据缺少稳定 ID")
        self._validate_export_id(export_id)
        package_format = self._validate_export_format(str(receipt.get("format") or ""))
        self._validate_receipt_content(receipt, content)
        with self._lock_for(run_id):
            data = self._read_unlocked(run_id)
            request_digest = str(receipt.get("request_digest") or "")
            requests = data.setdefault("export_requests", {})
            alias = requests.get(request_id)
            if isinstance(alias, dict):
                if alias.get("request_digest") != request_digest:
                    raise ValueError("同一 request_id 不能复用不同的导出参数")
                existing = self._receipt_by_id(data, str(alias.get("export_id") or ""))
                if not existing:
                    raise ValueError("导出请求映射的收据不存在")
                return copy.deepcopy(existing)
            existing = next((item for item in data.get("exports") or [] if item.get("request_id") == request_id), None)
            if existing:
                if existing.get("request_digest") != request_digest:
                    raise ValueError("同一 request_id 不能复用不同的导出参数")
                requests[request_id] = {"export_id": existing.get("export_id"), "request_digest": request_digest}
                self._persist(run_id, data)
                return copy.deepcopy(existing)
            selection_digest = str(receipt.get("selection_digest") or "")
            semantic_match = next((
                item for item in data.get("exports") or []
                if selection_digest and item.get("selection_digest") == selection_digest
            ), None)
            if semantic_match:
                requests[request_id] = {"export_id": semantic_match.get("export_id"), "request_digest": request_digest}
                self._persist(run_id, data)
                return copy.deepcopy(semantic_match)
            if expected_revision is not None and int(data.get("state_revision") or 0) != expected_revision:
                raise ValueError("运行状态在导出期间发生变化，请刷新后再导出")
            if self._receipt_by_id(data, export_id):
                raise ValueError("导出版本 ID 已存在")
            saved_receipt = copy.deepcopy(receipt)
            saved_receipt["version"] = max(
                [int(item.get("version") or 0) for item in data.get("exports") or []] or [0]
            ) + 1
            export_dir = self.run_dir(run_id) / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            path = export_dir / f"{export_id}.{package_format}"
            self._write_bytes(path, content)
            data.setdefault("exports", []).append(saved_receipt)
            requests[request_id] = {"export_id": export_id, "request_digest": request_digest}
            self._persist(run_id, data)
            return copy.deepcopy(saved_receipt)

    @staticmethod
    def _validate_export_id(export_id: str) -> None:
        if not isinstance(export_id, str) or not re.fullmatch(r"export-[A-Za-z0-9-]{8,160}", export_id):
            raise ValueError("Invalid export_id")

    @classmethod
    def _validate_export_format(cls, package_format: str) -> str:
        if package_format not in cls._EXPORT_FORMATS:
            raise ValueError("导出文件格式无效")
        return package_format

    @staticmethod
    def _receipt_by_id(data: dict[str, Any], export_id: str) -> dict[str, Any] | None:
        value = next((item for item in data.get("exports") or [] if item.get("export_id") == export_id), None)
        return value if isinstance(value, dict) else None

    @staticmethod
    def _validate_legacy_receipt_content(receipt: dict[str, Any], content: bytes) -> None:
        expected_sha = str(receipt.get("sha256") or "")
        if len(expected_sha) != 64 or hashlib.sha256(content).hexdigest() != expected_sha:
            raise ValueError("旧版导出收据与文件摘要校验失败")
        if int(receipt.get("size_bytes") or -1) != len(content):
            raise ValueError("旧版导出收据与文件大小校验失败")

    @staticmethod
    def _validate_receipt_content(receipt: dict[str, Any], content: bytes) -> None:
        expected_sha = str(receipt.get("sha256") or "")
        selection_digest = str(receipt.get("selection_digest") or "")
        if len(expected_sha) != 64 or hashlib.sha256(content).hexdigest() != expected_sha:
            raise ValueError("导出收据与文件摘要校验失败")
        if int(receipt.get("size_bytes") or -1) != len(content):
            raise ValueError("导出收据与文件大小校验失败")
        selection_snapshot = receipt.get("selection_snapshot")
        if len(selection_digest) != 64 or not isinstance(selection_snapshot, dict):
            raise ValueError("导出收据缺少冻结选择快照")
        canonical_snapshot = json.dumps(
            selection_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        if hashlib.sha256(canonical_snapshot).hexdigest() != selection_digest:
            raise ValueError("导出收据冻结选择摘要不一致")
        files = receipt.get("files") if isinstance(receipt.get("files"), list) else []
        if any(not isinstance(item, dict) or item.get("scope") not in {"package", "archive"} for item in files):
            raise ValueError("导出收据文件清单包含无效条目")
        package_files = [
            item for item in receipt.get("files") or []
            if isinstance(item, dict) and item.get("scope") == "package"
        ]
        package_file = package_files[0] if len(package_files) == 1 else None
        if not package_file or package_file.get("sha256") != expected_sha or int(package_file.get("size_bytes") or -1) != len(content):
            raise ValueError("导出收据文件清单不完整")
        archive_files = [
            item for item in receipt.get("files") or []
            if isinstance(item, dict) and item.get("scope") == "archive"
        ]
        if receipt.get("format") != "zip":
            if archive_files:
                raise ValueError("导出收据文件清单与格式不一致")
            return
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                actual_files = {}
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    payload = archive.read(info)
                    actual_files[info.filename] = {
                        "size_bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError("导出 ZIP 文件清单校验失败") from exc
        expected_files = {
            str(item.get("path") or ""): {
                "size_bytes": int(item.get("size_bytes") or -1),
                "sha256": str(item.get("sha256") or ""),
            }
            for item in archive_files
        }
        if (
            len(actual_files) != len(archive_files)
            or len(expected_files) != len(archive_files)
            or actual_files != expected_files
        ):
            raise ValueError("导出收据 ZIP 内部文件清单不一致")
