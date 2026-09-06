# 工作树清理记录（2026-08-15）

## 唯一生产入口

- 项目路径：`/Users/isla/Desktop/project/multi-stage-creation-model-end`
- 分支：`main`
- 基线提交：`19464b17 feat: enforce chapter titles and balanced prose length`
- GitHub：`github/main` 与本地基线一致
- 本地 Git 只保留 `github` remote；旧 Gitee `origin` 配置已移除（远程仓库本身未删除，URL 记录在备份 manifest）。
- 生产运行时：LangGraph `NarrativeExecutionService`，不保留旧 Runner、runtime selector 或 fallback 路径

本次清理移除了旧根目录脏副本、538c detached worktree、6ad8 临时 worktree 以及本地 codex/legacy 分支。6ad8 的未提交代码先完整迁入 canonical path，旧根目录和所有差异均已备份后才移入废纸篓。

## 外部备份

完整备份位于：

`/Users/isla/.codex/backups/yotsuba-ink-cleanup-20260815/`

备份包含三个 worktree 的提交号、状态、未跟踪文件清单和二进制 diff；源文件、运行数据、Provider profile/secret 数据库、历史文档、验收输出和依赖缓存分开保存。恢复前先阅读 `manifests/`，不要直接把旧目录重新注册为 worktree。

## 当前目录保留规则

- 保留：Phase 26/27 合同、DeepSeek Harness 评审、LangGraph runtime、三套 `official-deepseek-{fast,balanced,deep}.json`、当前测试和正式产品资源。
- 保留：`runtime/novel_workflow/native_runtime`、项目 JSON、Provider profile/secret 数据库等本地创作状态；这些不是源码，禁止按旧代码清理。
- 移出：Phase 9–25 历史方案、旧 roadmap、无关 Vue/SpringBoot 映射、Playwright/验收输出、偏好校准缓存和编译缓存。
- 隔离保留：`src/novel_workflow/archive/phase27_archive_reader.py` 是只读历史 Run 边界，不参与生产图，也没有执行、写回或恢复能力；生产切换完成前不得把 `native_runtime/runs` 当作 archive 根。

## 复核入口

清理后只允许出现一个 worktree：

```bash
git worktree list
git branch -avv
git status --short --branch
```

任何新阶段必须先更新 [`stage-artifact-contract.md`](./stage-artifact-contract.md)，再同步 LangGraph、官方模板、前端投影和测试。
