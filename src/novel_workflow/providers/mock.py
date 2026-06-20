from __future__ import annotations

import hashlib
from typing import Any

from novel_workflow.providers.base import ImageProvider, TextProvider


class MockTextProvider(TextProvider):
    name = "mock-text"

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        seed = str(context.get("title") or context.get("theme") or "未命名小说")
        digest = hashlib.sha1(f"{task_name}:{seed}:{prompt}".encode("utf-8")).hexdigest()[:8]
        title = context.get("title") or "潮雾旧声"
        if task_name == "info_recommend":
            return (
                f"# {title}\n\n"
                "分类：悬疑 / 都市奇想\n"
                "人物信息：林澈是旧港声纹档案修复师；许望舒是调查记者；周泊言是失踪案幸存者。\n"
                "故事背景：旧港区的雾钟会记录人们最不愿承认的声音。\n"
                f"简介：一次编号 {digest} 的磁带修复，让三人重新进入十年前的蓝潮禁区。"
            )
        if task_name == "summary":
            return (
                "全书梗概：主角团队从一盘异常磁带入手，追查旧港失踪案。"
                "他们逐步发现雾钟不是神秘灾厄，而是被人为改造的记忆记录装置。"
                "结局中，林澈公开档案，许望舒完成报道，周泊言找回被篡改的证词。"
            )
        if task_name == "outline":
            return "第一卷：磁带重现；第二卷：蓝潮禁区；第三卷：雾钟公开。"
        if task_name == "detail_outline":
            return (
                "第1章：林澈修复磁带，听见十年前自己的求救声。\n"
                "第2章：许望舒追踪磁带来源，发现旧港档案被删除。\n"
                "第3章：周泊言带二人进入蓝潮禁区，雾钟提前响起。\n"
                "第4章：三人找到实验室旧名单，确认记忆记录装置曾被用于证词筛选。\n"
                "第5章：沈白公开半份档案，林澈发现自己父亲参与过蓝潮计划。\n"
                "第6章：雾钟在全港响起，旧案幸存者的关系网第一次完整浮现。"
            )
        if task_name == "chapter_text":
            return (
                "第一章 雾钟未眠\n\n"
                "林澈把磁带放进修复机时，旧港的雾正贴着窗缝往里钻。"
                "机器转过第三圈，底噪里忽然浮出一个年轻的声音，喊着他的名字。"
                "那声音来自十年前，也来自他始终不肯打开的记忆。"
            )
        return f"{task_name} 输出：{prompt[:200]}"


class MockImageProvider(ImageProvider):
    name = "mock-image"

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": self.name,
            "prompt": prompt,
            "image_url": "https://placehold.co/768x1152/1f2937/f8fafc?text=Novel+Cover",
            "status": "mocked",
        }
