import json
import re
import requests


URL = "http://127.0.0.1:54862/v1/chat/completions"

payload = {
    "model": "ChiYong-MoE-Novel-18B-A6B",
    "messages": [
        {
            "role": "user",
            "content": """
    #### 角色:
    你是一位才华横溢的小说作家助手，擅长将小说基本信息转换为详细的小说描述。你的任务是根据提供的小说标题和分类，生成详细的小说信息，包括人物信息、故事背景和简介。请确保这些信息准确且具有吸引力。

    #### 输入:
    **小说标题**: 提供小说的标题。
    **分类**: 提供小说的分类信息。
    
    输出:
    请根据提供的小说标题和分类，生成详细的小说信息。输出应包括以下内容:
    人物信息: 列出主要角色的名字及其简短描述。
    故事背景: 描述故事发生的地点、时间和主要冲突。
    简介: 提供一个简短但吸引人的故事摘要。
    
    **小说标题**:
    箭楼奇遇

    **分类**:
    ['悬疑推理', '武侠小说', '仙侠玄幻']
    

    请根据以上信息，生成详细的小说信息。 
          """,
        }
    ],
    "stream": False,
}


def validate(content: str) -> None:
    assert "**人物信息**" in content, "missing 人物信息"
    assert "**故事背景**" in content, "missing 故事背景"
    assert "**简介**" in content, "missing 简介"
    assert "<|im_end|>" in content, "missing <|im_end|> end marker"
    m = re.search(r"\*\*人物信息\*\*:\s*([\s\S]*?)\n\s*\*\*故事背景\*\*", content)
    assert m is not None, "人物信息段提取失败"
    list_block = m.group(1)
    assert "[" in list_block and "]" in list_block, "人物信息不是列表格式"


def main() -> None:
    resp = requests.post(URL, json=payload, timeout=120)
    resp.raise_for_status()
    obj = resp.json()
    content = obj["choices"][0]["message"]["content"]
    validate(content)
    print("status: ok")
    print("model:", obj.get("model"))
    print("content_preview:")
    print(content[:1200])
    print("usage:", json.dumps(obj.get("usage", {}), ensure_ascii=False))


if __name__ == "__main__":
    main()

