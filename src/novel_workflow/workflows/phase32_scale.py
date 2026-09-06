"""Dormant Phase 32 route-specific scale and capacity contracts."""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_workflow.workflows.route_specs import CreationRouteId


ScaleUnit = Literal["minutes", "characters"]
ScaleProfileKind = Literal[
    "production",
    "release_smoke",
    "continuity_acceptance",
]


class ReleaseSmokeCapacity(BaseModel):
    """Internal caps for the 0.1.0 stability acceptance Runs."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    max_scenes: int | None = Field(default=None, ge=1, le=64)
    max_units: int | None = Field(default=None, ge=1, le=64)
    max_parts: int | None = Field(default=None, ge=1, le=9)
    max_volumes: int | None = Field(default=None, ge=1, le=50)
    max_chapters: int | None = Field(default=None, ge=1, le=400)

    @model_validator(mode="after")
    def require_at_least_one_cap(self) -> Self:
        if not any(
            value is not None
            for value in (
                self.max_scenes,
                self.max_units,
                self.max_parts,
                self.max_volumes,
                self.max_chapters,
            )
        ):
            raise ValueError("Release smoke capacity requires at least one cap")
        return self


class RollingWindowCapacity(BaseModel):
    """Bounded long-form planning window, independent of total book size."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    min_chapters: int = Field(ge=1, le=400)
    max_chapters: int = Field(ge=1, le=400)
    min_volumes: int = Field(ge=1, le=24)
    max_volumes: int = Field(ge=1, le=24)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.min_chapters > self.max_chapters:
            raise ValueError("Rolling window minimum chapters cannot exceed maximum")
        if self.min_volumes > self.max_volumes:
            raise ValueError("Rolling window minimum volumes cannot exceed maximum")
        return self

    def validate_request(self, *, chapters: int, volumes: int) -> None:
        if not self.min_chapters <= chapters <= self.max_chapters:
            raise ValueError(
                f"Rolling window chapters must be between {self.min_chapters} and "
                f"{self.max_chapters}"
            )
        if not self.min_volumes <= volumes <= self.max_volumes:
            raise ValueError(
                f"Rolling window volumes must be between {self.min_volumes} and "
                f"{self.max_volumes}"
            )


class ScalePolicy(BaseModel):
    """Route-owned P0 envelope and recommendation, before a Run is frozen."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    policy_id: str = Field(pattern=r"^length\.[a-z0-9_.-]+$")
    revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    route_id: CreationRouteId
    unit: ScaleUnit
    minimum: int = Field(ge=1)
    recommended_floor: int = Field(ge=1)
    recommended: int = Field(ge=1)
    recommended_ceiling: int = Field(ge=1)
    maximum: int = Field(ge=1)
    rationale: str = Field(min_length=1, max_length=1000)
    rolling_window: RollingWindowCapacity | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        values = (
            self.minimum,
            self.recommended_floor,
            self.recommended,
            self.recommended_ceiling,
            self.maximum,
        )
        if values != tuple(sorted(values)):
            raise ValueError("Scale envelope values must be monotonically ordered")
        if self.route_id == "long_novel" and self.rolling_window is None:
            raise ValueError("Long novel scale policy requires rolling window capacity")
        if self.route_id != "long_novel" and self.rolling_window is not None:
            raise ValueError("Only long novel scale policy may define rolling window capacity")
        expected_unit: ScaleUnit = "minutes" if self.route_id == "screenplay_sample" else "characters"
        if self.unit != expected_unit:
            raise ValueError("Scale unit does not match its creation route")
        return self

    def validate_target(self, target: int) -> None:
        if not self.minimum <= target <= self.maximum:
            raise ValueError(
                f"{self.route_id} target must be between {self.minimum} and {self.maximum}"
            )


class ScaleProfile(BaseModel):
    """Content-addressable values frozen into a Run definition."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    route_id: CreationRouteId
    policy_id: str = Field(pattern=r"^length\.[a-z0-9_.-]+$")
    policy_revision: str = Field(pattern=r"^r[1-9][0-9]*$")
    unit: ScaleUnit
    target: int = Field(ge=1)
    minimum: int = Field(ge=1)
    recommended_floor: int = Field(ge=1)
    recommended: int = Field(ge=1)
    recommended_ceiling: int = Field(ge=1)
    maximum: int = Field(ge=1)
    derivation_reason: str = Field(min_length=1, max_length=1000)
    rolling_window: RollingWindowCapacity | None = None
    profile_kind: ScaleProfileKind = "production"
    smoke_capacity: ReleaseSmokeCapacity | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        values = (
            self.minimum,
            self.recommended_floor,
            self.recommended,
            self.recommended_ceiling,
            self.maximum,
        )
        if values != tuple(sorted(values)):
            raise ValueError("Scale profile values must be monotonically ordered")
        if not self.minimum <= self.target <= self.maximum:
            raise ValueError("Scale profile target must remain inside its frozen envelope")
        expected_unit: ScaleUnit = "minutes" if self.route_id == "screenplay_sample" else "characters"
        if self.unit != expected_unit:
            raise ValueError("Scale profile unit does not match its creation route")
        if self.route_id == "long_novel" and self.rolling_window is None:
            raise ValueError("Long novel scale profile requires rolling window capacity")
        if self.route_id != "long_novel" and self.rolling_window is not None:
            raise ValueError("Only long novel scale profile may define rolling window capacity")
        if self.profile_kind == "production" and self.smoke_capacity is not None:
            raise ValueError("Production scale profile cannot carry release smoke capacity")
        if self.profile_kind == "release_smoke" and self.smoke_capacity is None:
            raise ValueError("Release smoke scale profile requires explicit capacity")
        if self.profile_kind == "continuity_acceptance":
            if self.route_id != "long_novel":
                raise ValueError(
                    "Continuity acceptance scale profile is private to long_novel"
                )
            if self.smoke_capacity is not None:
                raise ValueError(
                    "Continuity acceptance scale profile cannot carry release smoke capacity"
                )
            if self.rolling_window is None or (
                self.rolling_window.min_chapters,
                self.rolling_window.max_chapters,
                self.rolling_window.min_volumes,
                self.rolling_window.max_volumes,
            ) != (12, 12, 1, 1):
                raise ValueError(
                    "Continuity acceptance scale profile requires one exact 12-chapter window"
                )
        return self

    @property
    def uses_recommended_band(self) -> bool:
        return self.recommended_floor <= self.target <= self.recommended_ceiling


OFFICIAL_SCALE_POLICIES: Mapping[CreationRouteId, ScalePolicy] = MappingProxyType(
    {
        "screenplay_sample": ScalePolicy(
            policy_id="length.screenplay_sample.v1",
            revision="r1",
            route_id="screenplay_sample",
            unit="minutes",
            minimum=3,
            recommended_floor=8,
            recommended=12,
            recommended_ceiling=15,
            maximum=30,
            rationale="以可拍摄时长控制样片负载，优先验证动作、场景和对白是否成立。",
        ),
        "short_novel": ScalePolicy(
            policy_id="length.short_novel.v1",
            revision="r1",
            route_id="short_novel",
            unit="characters",
            minimum=2_000,
            recommended_floor=10_000,
            recommended=20_000,
            recommended_ceiling=30_000,
            maximum=130_000,
            rationale="以单体收束和读者承诺为中心，篇幅是软目标而非凑字数任务。",
        ),
        "long_novel": ScalePolicy(
            policy_id="length.long_novel.v1",
            revision="r1",
            route_id="long_novel",
            unit="characters",
            minimum=100_000,
            recommended_floor=100_000,
            recommended=150_000,
            recommended_ceiling=200_000,
            maximum=1_000_000,
            rationale="用 Part、Volume 和滚动 Window 管理长期连续性，先以 10-20 万字生产门验证。",
            rolling_window=RollingWindowCapacity(
                min_chapters=12,
                max_chapters=40,
                min_volumes=1,
                max_volumes=3,
            ),
        ),
    }
)


RELEASE_SMOKE_SCALE_POLICIES: Mapping[CreationRouteId, ScalePolicy] = MappingProxyType(
    {
        "screenplay_sample": ScalePolicy(
            policy_id="length.screenplay_sample.release_smoke.v1",
            revision="r1",
            route_id="screenplay_sample",
            unit="minutes",
            minimum=3,
            recommended_floor=3,
            recommended=3,
            recommended_ceiling=3,
            maximum=3,
            rationale="0.1.0 稳定性验收：限制为 3 分钟、最多 3 场，不改变剧本样片正式路线。",
        ),
        "short_novel": ScalePolicy(
            policy_id="length.short_novel.release_smoke.v1",
            revision="r1",
            route_id="short_novel",
            unit="characters",
            minimum=2_000,
            recommended_floor=2_000,
            recommended=3_500,
            recommended_ceiling=5_000,
            maximum=5_000,
            rationale="0.1.0 稳定性验收：限制为 2,000-5,000 字、最多 3 个正文单元。",
        ),
        "long_novel": ScalePolicy(
            policy_id="length.long_novel.release_smoke.v1",
            revision="r1",
            route_id="long_novel",
            unit="characters",
            minimum=100_000,
            recommended_floor=100_000,
            recommended=100_000,
            recommended_ceiling=200_000,
            maximum=1_000_000,
            rationale="0.1.0 稳定性验收：保持长篇正式篇幅下限，仅限制为 1 Part、1 卷、1 Window、2 章。",
            rolling_window=RollingWindowCapacity(
                min_chapters=2,
                max_chapters=2,
                min_volumes=1,
                max_volumes=1,
            ),
        ),
    }
)


CONTINUITY_ACCEPTANCE_SCALE_POLICIES: Mapping[CreationRouteId, ScalePolicy] = (
    MappingProxyType(
        {
            "long_novel": ScalePolicy(
                policy_id="length.long_novel.continuity_acceptance.v1",
                revision="r1",
                route_id="long_novel",
                unit="characters",
                minimum=100_000,
                recommended_floor=100_000,
                recommended=150_000,
                recommended_ceiling=200_000,
                maximum=1_000_000,
                rationale=(
                    "私有连续性验收：保持长篇正式篇幅合同，只冻结一个恰好 12 章的"
                    " Rolling Detail Window，用于接受前缀与恢复验证。"
                ),
                rolling_window=RollingWindowCapacity(
                    min_chapters=12,
                    max_chapters=12,
                    min_volumes=1,
                    max_volumes=1,
                ),
            )
        }
    )
)


def scale_policy(route_id: CreationRouteId) -> ScalePolicy:
    try:
        return OFFICIAL_SCALE_POLICIES[route_id]
    except KeyError as exc:
        raise ValueError(f"Unknown Phase 32 creation route: {route_id}") from exc


def release_smoke_scale_policy(route_id: CreationRouteId) -> ScalePolicy:
    """Return the private 0.1.0 acceptance envelope for one route."""

    try:
        return RELEASE_SMOKE_SCALE_POLICIES[route_id]
    except KeyError as exc:
        raise ValueError(f"Unknown Phase 32 release smoke route: {route_id}") from exc


def continuity_acceptance_scale_policy(route_id: CreationRouteId) -> ScalePolicy:
    """Return the private exact-12 long-form continuity acceptance envelope."""

    try:
        return CONTINUITY_ACCEPTANCE_SCALE_POLICIES[route_id]
    except KeyError as exc:
        raise ValueError(
            f"No Phase 32 continuity acceptance profile for route: {route_id}"
        ) from exc


def freeze_scale_profile(
    route_id: CreationRouteId,
    *,
    target: int | None = None,
    derivation_reason: str | None = None,
) -> ScaleProfile:
    """Resolve a route policy into the immutable values stored by a Run."""

    policy = scale_policy(route_id)
    resolved_target = policy.recommended if target is None else target
    policy.validate_target(resolved_target)
    return ScaleProfile(
        route_id=policy.route_id,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        unit=policy.unit,
        target=resolved_target,
        minimum=policy.minimum,
        recommended_floor=policy.recommended_floor,
        recommended=policy.recommended,
        recommended_ceiling=policy.recommended_ceiling,
        maximum=policy.maximum,
        derivation_reason=derivation_reason or policy.rationale,
        rolling_window=policy.rolling_window,
    )


def freeze_release_smoke_scale_profile(
    route_id: CreationRouteId,
    *,
    target: int | None = None,
    derivation_reason: str | None = None,
) -> ScaleProfile:
    """Freeze the private bounded profile used only by release acceptance."""

    policy = release_smoke_scale_policy(route_id)
    resolved_target = policy.recommended if target is None else target
    policy.validate_target(resolved_target)
    capacities = {
        "screenplay_sample": ReleaseSmokeCapacity(max_scenes=3),
        "short_novel": ReleaseSmokeCapacity(max_units=3),
        "long_novel": ReleaseSmokeCapacity(max_parts=1, max_volumes=1, max_chapters=2),
    }
    return ScaleProfile(
        route_id=policy.route_id,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        unit=policy.unit,
        target=resolved_target,
        minimum=policy.minimum,
        recommended_floor=policy.recommended_floor,
        recommended=policy.recommended,
        recommended_ceiling=policy.recommended_ceiling,
        maximum=policy.maximum,
        derivation_reason=derivation_reason or policy.rationale,
        rolling_window=policy.rolling_window,
        profile_kind="release_smoke",
        smoke_capacity=capacities[route_id],
    )


def freeze_continuity_acceptance_scale_profile(
    route_id: CreationRouteId,
    *,
    target: int | None = None,
    derivation_reason: str | None = None,
) -> ScaleProfile:
    """Freeze the private exact-12 profile used by the continuity harness only."""

    policy = continuity_acceptance_scale_policy(route_id)
    resolved_target = policy.recommended if target is None else target
    policy.validate_target(resolved_target)
    return ScaleProfile(
        route_id=policy.route_id,
        policy_id=policy.policy_id,
        policy_revision=policy.revision,
        unit=policy.unit,
        target=resolved_target,
        minimum=policy.minimum,
        recommended_floor=policy.recommended_floor,
        recommended=policy.recommended,
        recommended_ceiling=policy.recommended_ceiling,
        maximum=policy.maximum,
        derivation_reason=derivation_reason or policy.rationale,
        rolling_window=policy.rolling_window,
        profile_kind="continuity_acceptance",
    )


def validate_continuity_acceptance_chapter_counts(
    profile: ScaleProfile,
    *,
    window_chapter_counts: tuple[int, ...],
    window_volume_counts: tuple[int, ...] | None = None,
) -> None:
    """Enforce the frozen exact-12 aggregate at the Rolling Detail boundary.

    Production and release-smoke profiles keep their existing semantics.  The
    private continuity profile deliberately accepts exactly one 12-chapter
    Window, so neither a smaller fixture nor multiple partial Windows can be
    mistaken for the acceptance corpus.
    """

    if profile.profile_kind != "continuity_acceptance":
        return
    if profile.route_id != "long_novel" or profile.rolling_window is None:
        raise ValueError("Continuity acceptance requires a long_novel rolling window")
    expected = profile.rolling_window.min_chapters
    if profile.rolling_window.max_chapters != expected:
        raise ValueError("Continuity acceptance chapter count is not frozen exactly")
    actual_total = sum(window_chapter_counts)
    if actual_total != expected:
        raise ValueError(
            "Continuity acceptance Rolling Detail must contain exactly "
            f"{expected} chapters in total; received {actual_total}"
        )
    if window_chapter_counts != (expected,):
        raise ValueError(
            "Continuity acceptance Rolling Detail must contain exactly one "
            f"{expected}-chapter window; received {window_chapter_counts}"
        )
    if window_volume_counts is not None and window_volume_counts != (1,):
        raise ValueError(
            "Continuity acceptance Rolling Detail must contain exactly one "
            f"single-volume window; received {window_volume_counts}"
        )


__all__ = [
    "CONTINUITY_ACCEPTANCE_SCALE_POLICIES",
    "OFFICIAL_SCALE_POLICIES",
    "RELEASE_SMOKE_SCALE_POLICIES",
    "ReleaseSmokeCapacity",
    "RollingWindowCapacity",
    "ScaleProfileKind",
    "ScalePolicy",
    "ScaleProfile",
    "continuity_acceptance_scale_policy",
    "freeze_continuity_acceptance_scale_profile",
    "freeze_release_smoke_scale_profile",
    "freeze_scale_profile",
    "release_smoke_scale_policy",
    "scale_policy",
    "validate_continuity_acceptance_chapter_counts",
]
