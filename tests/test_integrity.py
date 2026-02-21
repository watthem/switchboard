"""Unit tests for _assess_integrity: all penalty paths and edge cases."""

from switchboard.v1.models import (
    AgentPolicy,
    AgentTelemetry,
    IntegrityPolicy,
    IntegrityStatus,
)
from switchboard.v1.services import _assess_integrity


def _policy(**kwargs) -> AgentPolicy:
    integrity = IntegrityPolicy(**kwargs)
    return AgentPolicy(agent_id="test", integrity=integrity)


def _telemetry(**kwargs) -> AgentTelemetry:
    return AgentTelemetry(agent_id="test", **kwargs)


# --- Perfect score ---


def test_perfect_score():
    policy = _policy(max_network_rtt_ms=120.0, max_network_jitter_ms=30.0)
    telemetry = _telemetry(network_rtt_ms=5.0, network_jitter_ms=1.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100
    assert result.status == IntegrityStatus.normal
    assert result.reasons == []


# --- No signals → unknown ---


def test_no_signals_unknown():
    policy = _policy()
    telemetry = _telemetry()
    result = _assess_integrity(policy, telemetry)
    assert result.status == IntegrityStatus.unknown


# --- Remote session ---


def test_remote_session_penalty():
    policy = _policy(allow_remote_session=False)
    telemetry = _telemetry(is_remote_session=True, network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 45
    assert "remote_session_detected" in result.reasons


def test_remote_session_allowed_no_penalty():
    policy = _policy(allow_remote_session=True)
    telemetry = _telemetry(is_remote_session=True, network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100


# --- Provider mismatch ---


def test_provider_mismatch():
    policy = _policy(expected_providers=["anthropic"])
    telemetry = _telemetry(observed_provider="openai", network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 35
    assert any("provider_mismatch" in r for r in result.reasons)


def test_provider_missing():
    policy = _policy(expected_providers=["anthropic"])
    telemetry = _telemetry(network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 10
    assert "provider_missing" in result.reasons


def test_provider_match_no_penalty():
    policy = _policy(expected_providers=["anthropic"])
    telemetry = _telemetry(observed_provider="anthropic", network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100


# --- Model mismatch ---


def test_model_mismatch():
    policy = _policy(expected_models=["claude-3"])
    telemetry = _telemetry(observed_model="gpt-4", network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 35
    assert any("model_mismatch" in r for r in result.reasons)


def test_model_missing():
    policy = _policy(expected_models=["claude-3"])
    telemetry = _telemetry(network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 10
    assert "model_missing" in result.reasons


# --- Region mismatch ---


def test_region_mismatch():
    policy = _policy(expected_regions=["us-east-1"])
    telemetry = _telemetry(observed_region="eu-west-1", network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 20
    assert any("region_mismatch" in r for r in result.reasons)


def test_region_missing():
    policy = _policy(expected_regions=["us-east-1"])
    telemetry = _telemetry(network_rtt_ms=5.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 5
    assert "region_missing" in result.reasons


# --- RTT penalties ---


def test_rtt_above_baseline():
    policy = _policy(max_network_rtt_ms=50.0)
    telemetry = _telemetry(network_rtt_ms=80.0)  # 1.6x, < 2x
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 20
    assert any("rtt_above_baseline" in r for r in result.reasons)


def test_rtt_far_above_baseline():
    policy = _policy(max_network_rtt_ms=50.0)
    telemetry = _telemetry(network_rtt_ms=100.0)  # 2.0x
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 35
    assert any("rtt_far_above_baseline" in r for r in result.reasons)


def test_rtt_within_limit_no_penalty():
    policy = _policy(max_network_rtt_ms=120.0)
    telemetry = _telemetry(network_rtt_ms=50.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100


# --- Jitter penalties ---


def test_jitter_above_baseline():
    policy = _policy(max_network_jitter_ms=30.0)
    telemetry = _telemetry(network_jitter_ms=45.0)  # 1.5x, < 2x
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 15
    assert any("jitter_above_baseline" in r for r in result.reasons)


def test_jitter_far_above_baseline():
    policy = _policy(max_network_jitter_ms=30.0)
    telemetry = _telemetry(network_jitter_ms=60.0)  # 2.0x
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100 - 25
    assert any("jitter_far_above_baseline" in r for r in result.reasons)


# --- Stacked penalties ---


def test_multiple_penalties_stack_to_degraded():
    """Remote session + provider mismatch + high RTT → degraded."""
    policy = _policy(
        allow_remote_session=False,
        expected_providers=["anthropic"],
        max_network_rtt_ms=50.0,
    )
    telemetry = _telemetry(
        is_remote_session=True,
        observed_provider="openai",
        network_rtt_ms=100.0,  # far above
    )
    result = _assess_integrity(policy, telemetry)
    # -45 (remote) -35 (provider) -35 (rtt far) = -115, clamped to 0
    assert result.score == 0
    assert result.status == IntegrityStatus.degraded


def test_elevated_score_range():
    """Score between 55-79 → elevated."""
    policy = _policy(max_network_rtt_ms=50.0, max_network_jitter_ms=20.0)
    telemetry = _telemetry(
        network_rtt_ms=80.0,  # -20
        network_jitter_ms=35.0,  # -15
    )
    result = _assess_integrity(policy, telemetry)
    assert result.score == 65
    assert result.status == IntegrityStatus.elevated


def test_score_clamped_to_zero():
    """Score can't go below 0."""
    policy = _policy(
        allow_remote_session=False,
        expected_providers=["a"],
        expected_models=["b"],
        expected_regions=["c"],
        max_network_rtt_ms=10.0,
        max_network_jitter_ms=5.0,
    )
    telemetry = _telemetry(
        is_remote_session=True,
        observed_provider="x",
        observed_model="y",
        observed_region="z",
        network_rtt_ms=100.0,
        network_jitter_ms=50.0,
    )
    result = _assess_integrity(policy, telemetry)
    assert result.score == 0
    assert result.status == IntegrityStatus.degraded


def test_no_rtt_limit_set_no_penalty():
    """When max_network_rtt_ms is None, no RTT penalty."""
    policy = _policy()  # no limits set
    telemetry = _telemetry(network_rtt_ms=9999.0)
    result = _assess_integrity(policy, telemetry)
    assert result.score == 100
