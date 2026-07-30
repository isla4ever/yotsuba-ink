from novel_workflow.orchestration.draft_candidate_artifacts import artifact_preview


def test_artifact_preview_never_falls_back_to_raw_json() -> None:
    preview = artifact_preview(
        {
            "schema_version": "internal-v1",
            "commit_signature": "private-signature",
            "nested": {"debug": True},
        }
    )

    assert preview == "候选产物已生成，当前结构暂不支持内容预览。"
    assert "schema_version" not in preview
    assert "{" not in preview


def test_artifact_preview_keeps_known_writer_facing_content() -> None:
    assert artifact_preview({"selected_title": "雾港", "synopsis": "旧案在潮汐中重现。"}) == "雾港\n旧案在潮汐中重现。"
