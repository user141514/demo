"""BMC 三维突破要素评分 — 算法验证测试"""

import pytest
from pydantic import ValidationError

from app.services.bmc_scoring_service import BMCScoringService
from app.schemas.bmc_scoring import BMCScoringSaveRequest, ModuleScoreInput


def test_calculate_cr_case():
    """产品文档 4.3 节案例：CR pain=4.5, data=2.0, feasibility=3.5"""
    svc = BMCScoringService()
    raw, norm = svc.calculate_single(4.5, 2.0, 3.5)
    assert raw == 3.825
    assert norm == 53.4


def test_calculate_extremes():
    """边界值测试"""
    svc = BMCScoringService()
    # 最高分
    raw_max, norm_max = svc.calculate_single(5.0, 5.0, 5.0)
    assert raw_max == 6.25
    assert norm_max == 100.0

    # 最低分
    raw_min, norm_min = svc.calculate_single(1.0, 1.0, 1.0)
    assert raw_min == 1.05
    assert norm_min == 0.0


def test_zone_quickwin():
    svc = BMCScoringService()
    assert svc.get_zone(4.0, 4.0, 70.0) == "quickwin"
    assert svc.get_zone(5.0, 5.0, 90.0) == "quickwin"


def test_zone_strategic():
    svc = BMCScoringService()
    assert svc.get_zone(4.5, 2.0, 53.0) == "strategic"
    assert svc.get_zone(4.0, 3.0, 55.0) == "strategic"


def test_zone_longterm():
    svc = BMCScoringService()
    assert svc.get_zone(3.0, 4.0, 45.0) == "longterm"


def test_zone_hold():
    svc = BMCScoringService()
    assert svc.get_zone(2.5, 2.0, 30.0) == "hold"


def test_veto_feasibility():
    svc = BMCScoringService()
    veto, reason = svc.get_veto_status(4.0, 3.0, 1.0)
    assert veto == "blocked_feasibility"
    assert reason is not None


def test_veto_data_pain():
    svc = BMCScoringService()
    veto, reason = svc.get_veto_status(3.0, 1.0, 4.0)
    assert veto == "blocked_data_pain"


def test_veto_pain_low():
    svc = BMCScoringService()
    veto, reason = svc.get_veto_status(2.0, 3.0, 3.0)
    assert veto == "not_recommended"


def test_evaluate_all():
    svc = BMCScoringService()
    modules = [
        ModuleScoreInput(key="customer_relationships", pain=4.5, data=2.0, feasibility=3.5),
        ModuleScoreInput(key="key_activities", pain=4.5, data=3.5, feasibility=4.0),
        ModuleScoreInput(key="key_resources", pain=4.0, data=2.5, feasibility=3.0),
        ModuleScoreInput(key="value_propositions", pain=3.0, data=3.0, feasibility=3.0),
        ModuleScoreInput(key="channels", pain=3.0, data=3.5, feasibility=3.5),
        ModuleScoreInput(key="customer_segments", pain=3.5, data=3.0, feasibility=3.5),
        ModuleScoreInput(key="revenue_streams", pain=3.0, data=3.0, feasibility=2.5),
        ModuleScoreInput(key="key_partnerships", pain=2.5, data=2.0, feasibility=3.0),
        ModuleScoreInput(key="cost_structure", pain=3.5, data=3.0, feasibility=3.5),
    ]
    result = svc.evaluate_all(modules, "test-001")
    assert len(result.top_3_keys) >= 2
    assert len(result.module_results) == 9


def test_top_3_matches_score_preview_instead_of_zone_priority():
    """Higher-scoring hold modules must not be skipped in favor of lower-scoring ones."""
    svc = BMCScoringService()
    modules = [
        ModuleScoreInput(key="key_resources", pain=3.5, data=5, feasibility=3),
        ModuleScoreInput(key="value_propositions", pain=3.5, data=3.5, feasibility=3.5),
        ModuleScoreInput(key="customer_segments", pain=3, data=3.5, feasibility=3.5),
        ModuleScoreInput(key="key_partnerships", pain=2.5, data=4, feasibility=3),
        ModuleScoreInput(key="key_activities", pain=2, data=2, feasibility=2),
    ]
    result = svc.evaluate_all(modules)
    assert result.top_3_keys == [
        "key_resources", "value_propositions", "customer_segments"
    ]
    assert result.top_3_keys == [
        item.key for item in sorted(
            result.module_results,
            key=lambda item: item.normalized_score,
            reverse=True,
        )[:3]
    ]


def test_top3_is_the_same_score_ranking_even_when_risk_labels_differ():
    svc = BMCScoringService()
    modules = [
        ModuleScoreInput(key="key_resources", pain=2, data=5, feasibility=5),
        ModuleScoreInput(key="value_propositions", pain=3, data=3, feasibility=3),
        ModuleScoreInput(key="customer_segments", pain=3, data=3, feasibility=2),
        ModuleScoreInput(key="key_partnerships", pain=2.5, data=2, feasibility=3),
    ]
    result = svc.evaluate_all(modules)
    ranked = sorted(result.module_results, key=lambda item: -item.normalized_score)
    assert result.top_3_keys == [item.key for item in ranked[:3]]
    assert result.top_3_results[0].veto_status == "not_recommended"


def test_unknown_and_duplicate_module_scores_are_rejected():
    with pytest.raises(ValidationError):
        ModuleScoreInput(key="anything", pain=3, data=3, feasibility=3)
    item = ModuleScoreInput(key="key_resources", pain=3, data=3, feasibility=3)
    with pytest.raises(ValidationError):
        BMCScoringSaveRequest(selected_keys=[item.key], all_module_scores=[item, item])


def test_single_breakthrough_selection_is_valid():
    request = BMCScoringSaveRequest(
        selected_keys=["key_resources"],
        all_module_scores=[
            ModuleScoreInput(key="key_resources", pain=3.5, data=5, feasibility=3),
        ],
    )
    assert request.selected_keys == ["key_resources"]


def test_complementarity_warning():
    svc = BMCScoringService()
    # 全部为内部效率类
    warning = svc.check_complementarity(
        ["key_activities", "key_resources", "cost_structure"]
    )
    assert warning is not None
    assert "内部效率" in warning

    # 混合
    no_warning = svc.check_complementarity(
        ["key_activities", "customer_relationships", "cost_structure"]
    )
    assert no_warning is None
