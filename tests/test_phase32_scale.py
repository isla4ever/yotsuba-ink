from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.phase32_route_artifacts import (
    NovelBriefArtifact,
    bind_phase32_artifact,
)
from novel_workflow.workflows.phase32_scale import (
    CONTINUITY_ACCEPTANCE_SCALE_POLICIES,
    OFFICIAL_SCALE_POLICIES,
    RELEASE_SMOKE_SCALE_POLICIES,
    ReleaseSmokeCapacity,
    RollingWindowCapacity,
    ScalePolicy,
    ScaleProfile,
    continuity_acceptance_scale_policy,
    freeze_continuity_acceptance_scale_profile,
    freeze_release_smoke_scale_profile,
    freeze_scale_profile,
    release_smoke_scale_policy,
    scale_policy,
    validate_continuity_acceptance_chapter_counts,
)


def test_official_scale_policies_encode_three_route_units_and_envelopes() -> None:
    assert tuple(OFFICIAL_SCALE_POLICIES) == (
        "screenplay_sample",
        "short_novel",
        "long_novel",
    )
    screenplay = scale_policy("screenplay_sample")
    short_novel = scale_policy("short_novel")
    long_novel = scale_policy("long_novel")

    assert (screenplay.unit, screenplay.minimum, screenplay.recommended, screenplay.maximum) == (
        "minutes",
        3,
        12,
        30,
    )
    assert (short_novel.unit, short_novel.minimum, short_novel.recommended, short_novel.maximum) == (
        "characters",
        2_000,
        20_000,
        130_000,
    )
    assert long_novel.rolling_window is not None
    assert (long_novel.minimum, long_novel.recommended, long_novel.maximum) == (
        100_000,
        150_000,
        1_000_000,
    )


def test_freeze_scale_profile_defaults_and_allows_explicit_soft_target() -> None:
    default = freeze_scale_profile("short_novel")
    custom = freeze_scale_profile(
        "short_novel",
        target=60_000,
        derivation_reason="作者选择单体中篇长度。",
    )

    assert default.target == 20_000
    assert default.uses_recommended_band is True
    assert custom.target == 60_000
    assert custom.uses_recommended_band is False
    assert custom.derivation_reason == "作者选择单体中篇长度。"


@pytest.mark.parametrize(
    ("route_id", "target"),
    [
        ("screenplay_sample", 2),
        ("screenplay_sample", 31),
        ("short_novel", 1_999),
        ("short_novel", 130_001),
        ("long_novel", 99_999),
        ("long_novel", 1_000_001),
    ],
)
def test_freeze_scale_profile_rejects_targets_outside_p0_envelope(
    route_id: str,
    target: int,
) -> None:
    with pytest.raises(ValueError, match="target must be between"):
        freeze_scale_profile(route_id, target=target)  # type: ignore[arg-type]


def test_long_novel_window_capacity_is_independent_and_bounded() -> None:
    profile = freeze_scale_profile("long_novel")
    assert profile.rolling_window is not None
    profile.rolling_window.validate_request(chapters=24, volumes=2)

    with pytest.raises(ValueError, match="chapters must be between"):
        profile.rolling_window.validate_request(chapters=8, volumes=2)
    with pytest.raises(ValueError, match="volumes must be between"):
        profile.rolling_window.validate_request(chapters=24, volumes=4)


def test_release_smoke_profiles_are_explicit_and_do_not_weaken_production_policy() -> None:
    assert tuple(RELEASE_SMOKE_SCALE_POLICIES) == tuple(OFFICIAL_SCALE_POLICIES)
    screenplay = freeze_release_smoke_scale_profile("screenplay_sample")
    short_novel = freeze_release_smoke_scale_profile("short_novel")
    long_novel = freeze_release_smoke_scale_profile("long_novel")

    assert screenplay.profile_kind == "release_smoke"
    assert screenplay.smoke_capacity is not None
    assert screenplay.smoke_capacity.max_scenes == 3
    assert short_novel.target == 3_500
    assert short_novel.smoke_capacity is not None
    assert short_novel.smoke_capacity.max_units == 3
    assert long_novel.target == 100_000
    assert long_novel.rolling_window is not None
    assert (long_novel.rolling_window.min_chapters, long_novel.rolling_window.max_chapters) == (2, 2)
    assert long_novel.smoke_capacity is not None
    assert (long_novel.smoke_capacity.max_parts, long_novel.smoke_capacity.max_volumes) == (1, 1)
    assert scale_policy("long_novel").minimum == 100_000


def test_release_smoke_capacity_requires_a_declared_cap() -> None:
    with pytest.raises(ValidationError, match="at least one cap"):
        ReleaseSmokeCapacity()

    with pytest.raises(ValidationError, match="Production scale profile"):
        production = freeze_scale_profile("short_novel").model_dump(mode="json")
        production["smoke_capacity"] = {"max_units": 3}
        ScaleProfile.model_validate(production)


def test_release_smoke_policy_is_separate_from_the_official_production_policy() -> None:
    assert release_smoke_scale_policy("long_novel").policy_id != scale_policy("long_novel").policy_id
    with pytest.raises(ValueError, match="target must be between"):
        freeze_release_smoke_scale_profile("short_novel", target=5_001)


def test_long_release_smoke_target_remains_valid_for_the_long_brief_contract() -> None:
    profile = freeze_release_smoke_scale_profile("long_novel")
    brief = NovelBriefArtifact(
        title="档案潮汐",
        premise="档案修复师追查一份尚未发生的灾难记录。",
        audience_promise="读者会跟随证词来源逐步判断谁在改写城市记忆。",
        theme_question="如果记忆可以被重写，什么仍然算作证据？",
        world_rules=("正式档案的修改必须留下可核验的签名链。",),
        ending_direction="主角保住原始证词，但暴露了更大的改写网络。",
        narrative_voice="克制、具体、以行动和证据推进。",
        target_characters=profile.target,
    )
    assert bind_phase32_artifact("long_novel", "brief", brief) is brief


def test_continuity_acceptance_profile_is_private_to_one_exact_12_chapter_window() -> None:
    assert tuple(CONTINUITY_ACCEPTANCE_SCALE_POLICIES) == ("long_novel",)
    profile = freeze_continuity_acceptance_scale_profile("long_novel")

    assert profile.profile_kind == "continuity_acceptance"
    assert profile.policy_id == "length.long_novel.continuity_acceptance.v1"
    assert profile.rolling_window is not None
    assert (
        profile.rolling_window.min_chapters,
        profile.rolling_window.max_chapters,
        profile.rolling_window.min_volumes,
        profile.rolling_window.max_volumes,
    ) == (12, 12, 1, 1)
    assert continuity_acceptance_scale_policy("long_novel") != scale_policy(
        "long_novel"
    )

    with pytest.raises(ValueError, match="No Phase 32 continuity acceptance profile"):
        freeze_continuity_acceptance_scale_profile("short_novel")


@pytest.mark.parametrize("chapter_count", (8, 10, 11, 13))
def test_continuity_acceptance_rejects_non_exact_chapter_totals(
    chapter_count: int,
) -> None:
    profile = freeze_continuity_acceptance_scale_profile("long_novel")

    with pytest.raises(ValueError, match="exactly 12 chapters in total"):
        validate_continuity_acceptance_chapter_counts(
            profile,
            window_chapter_counts=(chapter_count,),
        )


def test_continuity_acceptance_accepts_only_one_complete_12_chapter_window() -> None:
    profile = freeze_continuity_acceptance_scale_profile("long_novel")

    validate_continuity_acceptance_chapter_counts(
        profile,
        window_chapter_counts=(12,),
    )
    with pytest.raises(ValueError, match="exactly one 12-chapter window"):
        validate_continuity_acceptance_chapter_counts(
            profile,
            window_chapter_counts=(6, 6),
        )
    with pytest.raises(ValueError, match="single-volume window"):
        validate_continuity_acceptance_chapter_counts(
            profile,
            window_chapter_counts=(12,),
            window_volume_counts=(2,),
        )


def test_scale_contracts_reject_invalid_order_units_and_extra_fields() -> None:
    with pytest.raises(ValidationError, match="monotonically ordered"):
        ScalePolicy(
            policy_id="length.short_novel.test",
            revision="r1",
            route_id="short_novel",
            unit="characters",
            minimum=10,
            recommended_floor=30,
            recommended=20,
            recommended_ceiling=40,
            maximum=50,
            rationale="invalid order",
        )

    with pytest.raises(ValidationError, match="unit"):
        ScalePolicy(
            policy_id="length.short_novel.test",
            revision="r1",
            route_id="short_novel",
            unit="minutes",
            minimum=10,
            recommended_floor=20,
            recommended=30,
            recommended_ceiling=40,
            maximum=50,
            rationale="invalid unit",
        )

    with pytest.raises(ValidationError, match="extra"):
        RollingWindowCapacity.model_validate(
            {
                "min_chapters": 12,
                "max_chapters": 40,
                "min_volumes": 1,
                "max_volumes": 3,
                "quality_mode": "fast",
            }
        )


def test_phase32_scale_source_isolated_from_legacy_scale_runtime() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/workflows/phase32_scale.py"
    ).read_text(encoding="utf-8")
    assert "narrative_scale" not in source
    assert "quality_mode" not in source
    assert "STAGE_ORDER" not in source
