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
        "max_tokens": 1800,
    }
    cases = []

    p1 = (
        "\n            #### 角色：\n"
        "            你是一位才华横溢的小说作家助手，擅长将小说的主要人物、故事背景和简介转换为分卷大纲。\n"
        "            你的任务是根据提供的基本信息，生成多个详细的分卷梗概，供后续按卷拆章使用。\n\n"
        "            #### 输入：\n"
        "            1. **主要人物**：提供小说中的主要人物及其关键行为。\n"
        "            2. **故事背景**：提供小说的故事背景信息。\n"
        "            3. **简介**：提供小说的简短简介。\n\n"
        "            #### 输出（必须严格遵守）：\n"
        "            返回一个列表字符串，每个元素是一个JSON对象：\n"
        "            {'主要人物和他们的行为': {str:str,...}, '故事情节': {'开始':str, '发展':str, '高潮':str, '结局':str}}\n"
        "            要求：\n"
        "            - 至少输出3个分卷对象，建议4个；\n"
        "            - 每卷人物行为具体，不重复堆砌模板句；\n"
        "            - 每卷四段故事都要完整，能支撑后续拆章。\n"
        "            - 不要输出代码块，不要输出额外解释。\n\n"
        "            **小说标题**：\n"
        "            昆仑镜下\n\n"
        "            **主要人物**：\n"
        "            {'韩子陌':'在医术与武学之间寻找自证路径，连续推进调查与试炼。',"
        "            '韩子盛':'围绕家族线索组织行动，承担关键节点的对抗任务。',"
        "            '羽漠尘':'在高压冲突中提供资源与判断，推动主线多次转向。',"
        "            '赵开':'掌握门派与会场信息流，在关键环节影响事件节奏。'}\n\n"
        "            **故事背景**：\n"
        "            故事发生在一个医学、武艺并行的世界。封丹会牵出旧案与门派博弈，昆仑山下暗潮涌动。\n\n"
        "            **简介**：\n"
        "            韩子陌因无法封丹而屡遭轻视，却在追查本惜草来源时卷入更深的权力争斗。随着谈溪谷案情反复，"
        "            她与韩子盛、羽漠尘等人的关系持续重构。真相不止关乎个人命运，也关乎数个势力的存亡边界。\n\n"
        "            请根据以上信息生成分卷大纲。\n"
    )
    c1 = dict(base)
    c1["messages"] = [{"role": "user", "content": p1}]
    cases.append(("wuxia_medical", c1))

    p2 = (
        "\n            #### 角色：\n"
        "            你是一位资深叙事策划师。请把输入的角色行为、背景和简介，转成可拆章的多分卷大纲。\n\n"
        "            #### 输出格式（固定）：\n"
        "            [\n"
        "              {'主要人物和他们的行为': {...}, '故事情节': {'开始':..., '发展':..., '高潮':..., '结局':...}},\n"
        "              ...\n"
        "            ]\n"
        "            至少3卷，每卷必须有不同冲突重心与阶段性结局。\n\n"
        "            **小说标题**：\n"
        "            雨巷追光计划\n\n"
        "            **主要人物**：\n"
        "            {'沈念':'持续追踪旧城改造中的失踪档案并对接关键证人。',"
        "            '顾临川':'在调查推进中搭建证据链并承担现场突破。',"
        "            '林晚棠':'负责舆情和媒体口径，稳定外部压力。',"
        "            '周野':'渗透灰色产业链获取上游交易线索。',"
        "            '程霁':'整理历史卷宗并校验时间线异常。'}\n\n"
        "            **故事背景**：\n"
        "            近未来滨海都市推进旧城改造，连环失踪案与地产并购同步出现。公共记忆被篡改，资本和政务边界模糊。\n\n"
        "            **简介**：\n"
        "            沈念在重启父亲遗留调查后，发现多年前档案被人为切割。团队在官方程序、媒体战和地下交易网之间反复拉扯，"
        "            每次突破都会引发新的反噬。真相逐步指向一套“合法外衣下的系统性清除机制”。\n\n"
        "            请根据以上信息生成分卷大纲。\n"
    )
    c2 = dict(base)
    c2["messages"] = [{"role": "user", "content": p2}]
    cases.append(("urban_suspense", c2))

    p3 = (
        "\n            #### 角色：\n"
        "            你是长篇网文总策划。请将人物行为与主线简介细化为分卷大纲，服务后续分章细纲。\n\n"
        "            #### 固定输出：\n"
        "            每卷返回 {'主要人物和他们的行为': {...}, '故事情节': {'开始':..., '发展':..., '高潮':..., '结局':...}}\n"
        "            整体以列表形式输出，3-4卷。\n\n"
        "            **小说标题**：\n"
        "            火星回廊协议\n\n"
        "            **主要人物**：\n"
        "            {'陆岚':'带队修复火星轨道站失控模块并定位异常指令源。',"
        "            '秦渡':'负责舰队调度与对外谈判，控制冲突升级速度。',"
        "            '许闻声':'解析古旧信标与黑箱数据，推进技术线反转。',"
        "            '白栀':'在殖民地内部组织撤离并维持民用秩序。',"
        "            '唐骁':'执行高风险外勤和封锁任务，承担正面冲突。'}\n\n"
        "            **故事背景**：\n"
        "            23世纪，人类在火星建立多层回廊城市。能源寡头与自治议会长期博弈，轨道防御系统出现异常重启。\n\n"
        "            **简介**：\n"
        "            一次看似普通的维护任务揭开了“回廊协议”被篡改的事实。陆岚团队在资源断供、舆论操控和军事威慑下连续推进，"
        "            试图找出谁在利用系统故障制造新秩序。随着黑箱真相曝光，殖民地必须在安全与自由之间做出代价极高的选择。\n\n"
        "            请根据以上信息生成分卷大纲。\n"
    )
    c3 = dict(base)
    c3["messages"] = [{"role": "user", "content": p3}]
    cases.append(("scifi_colony", c3))

    return cases


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
    ap = argparse.ArgumentParser(description="Launch local server, run 3 outline tests, save responses.")
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--port", type=int, default=54862)
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

    out_log = logs_dir / "_outline_server_v8_one_shot.out.log"
    err_log = logs_dir / "_outline_server_v8_one_shot.err.log"

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
            req_path = logs_dir / f"_outline_case{idx}_{name}_request.json"
            rsp_path = logs_dir / f"_outline_case{idx}_{name}_response.json"
            txt_path = logs_dir / f"_outline_case{idx}_{name}_content.txt"

            req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            r = requests.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                timeout=180,
            )
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
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
