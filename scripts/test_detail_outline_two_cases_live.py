"""
Launch local server, run 2 detail-outline tests, save responses.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests


def _case_payloads():
    base = {
        "model": "ChiYong-MoE-Novel-18B-A6B",
        "stream": False,
        "temperature": 0.72,
        "top_p": 0.88,
        "max_tokens": 2600,
    }

    c1_prompt = """
#### 角色：
你是一位资深小说章节策划助手。请把给定分卷梗概细化为可直接写作的章节细纲。

#### 输出格式（必须严格遵守）：
只输出一个列表字符串，列表每项为：
{'章节标题': str, '细纲内容': str}
共输出 3 项，按列表顺序表示章节先后。

**小说标题**：
冬以嫣的青春之旅

**人物信息**：
{'冬以嫣': '创办爱心社团并组织公益行动，在友情冲突中承担协调任务。', '阮桐': '在亲密关系中经历误解、分手与重建。', '白轩': '在情感选择中摇摆并尝试修复关系。', '何思颖': '在竞争关系中做出放手决定并推动矛盾收束。'}

**小说部分内容的梗概**：
本卷围绕大学第一学期的社团成长与情感纠葛展开。冬以嫣在公益行动中建立影响力，阮桐在亲密关系中遭遇反复，友情与爱情在同一时间窗持续拉扯。

**小说简介**：
《冬以嫣的青春之旅》讲述青年人在成长阶段处理理想、关系与现实代价的过程，故事强调人物行动与情感变化的因果关联。

**章节划分**：
一共 3 章
""".strip()

    c2_prompt = """
#### 角色：
你是一位资深小说章节策划助手。请把给定分卷梗概细化为可直接写作的章节细纲。

#### 输出格式（必须严格遵守）：
只输出一个列表字符串，列表每项为：
{'章节标题': str, '细纲内容': str}
共输出 4 项，按列表顺序表示章节先后。

**小说标题**：
火星回廊协议

**人物信息**：
{'陆岚': '带队追查协议篡改源头，平衡技术线和行动线。', '秦渡': '负责调度与对外谈判，在危机升级时压住冲突扩散。', '许闻声': '解密黑箱数据并提供关键反证。', '白栀': '组织居民疏散并维持内部秩序。'}

**小说部分内容的梗概**：
本卷聚焦回廊协议被篡改后的应急处置。调查线、政治线和民生线并行推进，主角组在资源断供和舆论压力下完成阶段反击。

**小说简介**：
《火星回廊协议》以近未来殖民社会为背景，围绕安全、自治与权力边界展开多线冲突，强调技术决策与人性选择的双重代价。

**章节划分**：
一共 4 章
""".strip()

    c1 = dict(base)
    c1["messages"] = [{"role": "user", "content": c1_prompt}]

    c2 = dict(base)
    c2["messages"] = [{"role": "user", "content": c2_prompt}]

    return [("campus", c1), ("scifi", c2)]


def wait_health(base_url: str, timeout_s: int = 900) -> None:
    start = time.time()
    last_err = None
    while time.time() - start < timeout_s:
        try:
            r = requests.get(f"{base_url}/health", timeout=3)
            if r.status_code == 200:
                return
            last_err = f"health status={r.status_code} body={r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(2)
    raise RuntimeError(f"server health check timeout, last_err={last_err}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Launch local server, run 2 detail-outline tests, save responses.")
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--port", type=int, default=54866)
    ap.add_argument(
        "--adapter-path",
        default="outputs/outline_hqcorr_resilient_outline1000_long_v2/outline_hqcorr_len224_r4/final",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    py = root / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(sys.executable)

    out_log = logs_dir / "_detail_outline_server_one_shot.out.log"
    err_log = logs_dir / "_detail_outline_server_one_shot.err.log"

    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = args.api_key
    env.setdefault("PYTHONIOENCODING", "utf-8")

    cmd = [
        str(py),
        "deploy/openai_compat_server.py",
        "--model-path",
        r"D:\models\Qwen3.5-4B",
        "--served-model-name",
        "ChiYong-MoE-Novel-18B-A6B",
        "--adapter-path",
        args.adapter_path,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--device",
        "auto",
        "--upstream-endpoint",
        "https://api.deepseek.com/v1/chat/completions",
        "--upstream-model",
        "deepseek-chat",
        "--upstream-api-key-env",
        "DEEPSEEK_API_KEY",
        "--upstream-timeout-seconds",
        "120",
        "--upstream-nonstream-tasks",
        "info_recommend,summary,outline,detail_outline",
    ]

    proc = None
    try:
        with out_log.open("w", encoding="utf-8") as fout, err_log.open("w", encoding="utf-8") as ferr:
            proc = subprocess.Popen(
                cmd,
                cwd=str(root),
                stdout=fout,
                stderr=ferr,
                env=env,
            )

        base_url = f"http://127.0.0.1:{args.port}"
        wait_health(base_url, timeout_s=1200)

        for idx, (name, payload) in enumerate(_case_payloads(), start=1):
            req_path = logs_dir / f"_detail_outline_case{idx}_{name}_request.json"
            rsp_path = logs_dir / f"_detail_outline_case{idx}_{name}_response.json"
            txt_path = logs_dir / f"_detail_outline_case{idx}_{name}_content.txt"

            req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            r = requests.post(f"{base_url}/v1/chat/completions", json=payload, timeout=240)
            obj = r.json()
            rsp_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

            content = ""
            try:
                content = str(obj["choices"][0]["message"]["content"])
            except Exception:
                content = ""
            txt_path.write_text(content, encoding="utf-8")

            print(f"[ok] case{idx} {name} status={r.status_code} -> {rsp_path.name}")

        print(f"[done] out_log={out_log} err_log={err_log}")
        return 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
