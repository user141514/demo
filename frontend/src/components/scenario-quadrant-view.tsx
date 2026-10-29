"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  apiBaseUrl,
  formatMutationError,
  updateScenarioPool,
  saveTop3Scenarios,
} from "@/lib/api";
import type {
  ScenarioRecommendationItem,
  ScenarioRecommendationResult,
} from "@/lib/types";
import { assessmentKeys } from "@/hooks/use-assessment";
import { toast } from "@/hooks/use-toast";

const QUADRANT_THRESHOLD = 3.5;
const WEIGHT_X = 0.6;
const WEIGHT_Y_INV = 0.4;
const Y_INVERSION_BASE = 6;
const LPS_DISPLAY_MULTIPLIER = 2;
const IMMEDIATE_START_THRESHOLD = 8.0;
const PLAN_ADVANCE_THRESHOLD = 5.0;

type QuadrantLabel =
  | "AI优先区"
  | "自动化主战场"
  | "人机协作区"
  | "人类保留区";

type EditableScenario = ScenarioRecommendationItem & {
  _x: number;
  _y: number;
  _qs: number;
  _lps: number;
  _lpsDisplay: number;
  _quadrant: QuadrantLabel;
  _tier: number;
  _level: string;
  _kappa: number;
};

type SaveStatus = "idle" | "saving" | "saved" | "error";

const QUADRANT_META: Record<
  QuadrantLabel,
  {
    badgeClass: string;
    bubbleColor: string;
    areaClass: string;
    areaLabelClass: string;
    borderClass: string;
  }
> = {
  自动化主战场: {
    badgeClass: "badge-success",
    bubbleColor: "#10b981",
    areaClass: "bg-emerald-50/50",
    areaLabelClass: "text-emerald-400/70",
    borderClass: "border-emerald-300",
  },
  AI优先区: {
    badgeClass: "badge-warning",
    bubbleColor: "#f59e0b",
    areaClass: "bg-amber-50/50",
    areaLabelClass: "text-amber-400/70",
    borderClass: "border-amber-300",
  },
  人机协作区: {
    badgeClass: "badge-info",
    bubbleColor: "#0ea5e9",
    areaClass: "bg-sky-50/50",
    areaLabelClass: "text-sky-400/70",
    borderClass: "border-sky-300",
  },
  人类保留区: {
    badgeClass: "badge-muted",
    bubbleColor: "#94a3b8",
    areaClass: "bg-slate-50/70",
    areaLabelClass: "text-slate-400/70",
    borderClass: "border-slate-300",
  },
};

const X_DESCRIPTIONS: Record<number, string> = {
  1: "完全非结构化，暂不适合直接做成 AI 场景。",
  2: "低度结构化，需要先补规则和字段定义。",
  3: "中度结构化，可以先在局部场景试点。",
  4: "高度结构化，大部分流程已经标准化。",
  5: "完全结构化，适合优先沉淀为规模化 AI 能力。",
};

const Y_DESCRIPTIONS: Record<number, string> = {
  1: "复杂度很低，适合快速落地。",
  2: "复杂度较低，规则可以较快梳理清楚。",
  3: "复杂度中等，需要一定的跨岗位协同。",
  4: "复杂度较高，涉及多变量判断与流程改造。",
  5: "复杂度很高，落地阻力和改造成本都更高。",
};

const RANK_EMOJI = ["🥇", "🥈", "🥉"];
const SCENE_ORDINAL = ["一", "二", "三"];
const RANK_ACCENT_BG = ["bg-amber-400", "bg-slate-300", "bg-stone-400"];
const MAX_SCENARIO_TEASER_LENGTH = 15;

function calcQuadrant(x: number, y: number): QuadrantLabel {
  if (x >= QUADRANT_THRESHOLD && y >= QUADRANT_THRESHOLD) return "AI优先区";
  if (x >= QUADRANT_THRESHOLD && y < QUADRANT_THRESHOLD) return "自动化主战场";
  if (x < QUADRANT_THRESHOLD && y >= QUADRANT_THRESHOLD) return "人机协作区";
  return "人类保留区";
}

function calcTier(quadrant: QuadrantLabel): number {
  if (quadrant === "自动化主战场") return 1;
  if (quadrant === "AI优先区") return 2;
  if (quadrant === "人机协作区") return 3;
  return 4;
}

function calcLevel(lpsDisplay: number): string {
  if (lpsDisplay >= IMMEDIATE_START_THRESHOLD) return "立即启动";
  if (lpsDisplay >= PLAN_ADVANCE_THRESHOLD) return "规划推进";
  return "持续观察";
}

function recompute(x: number, y: number, kappa = 1) {
  const qs = +(x * y).toFixed(1);
  const lps = +(x * WEIGHT_X + (Y_INVERSION_BASE - y) * WEIGHT_Y_INV).toFixed(4);
  const lpsDisplay = +(lps * kappa * LPS_DISPLAY_MULTIPLIER).toFixed(1);
  const quadrant = calcQuadrant(x, y);
  const tier = calcTier(quadrant);
  const level = calcLevel(lpsDisplay);
  return { qs, lps, lpsDisplay, quadrant, tier, level };
}

function toEditable(item: ScenarioRecommendationItem): EditableScenario {
  const x = item.priority_structuredness_x ?? 3;
  const y = item.priority_complexity_y ?? 3;
  const kappa = item.industry_coefficient ?? 1;
  const { qs, lps, lpsDisplay, quadrant, tier, level } = recompute(x, y, kappa);

  return {
    ...item,
    _x: x,
    _y: y,
    _qs: qs,
    _lps: lps,
    _lpsDisplay: lpsDisplay,
    _quadrant: quadrant,
    _tier: tier,
    _level: item.recommendation_level || level,
    _kappa: kappa,
  };
}

function buildScenarioBuckets(recommendation: ScenarioRecommendationResult) {
  const activeSource = recommendation.all_scores ?? recommendation.top_scenarios;
  const excludedSource = recommendation.excluded_scores ?? [];
  const topIds = new Set(recommendation.top_scenarios.map((item) => item.scenario_id));
  const byId = new Map(activeSource.map((item) => [item.scenario_id, item]));
  const topItems = recommendation.top_scenarios
    .map((item) => byId.get(item.scenario_id) ?? item)
    .filter(Boolean) as ScenarioRecommendationItem[];
  const restItems = activeSource.filter((item) => !topIds.has(item.scenario_id));

  return {
    active: [...topItems, ...restItems].map(toEditable),
    excluded: excludedSource.map(toEditable),
  };
}

function buildOptimisticScenarioRecommendation(
  recommendation: ScenarioRecommendationResult,
  rankedItems: ScenarioRecommendationItem[],
  nextActiveIds: string[],
): ScenarioRecommendationResult {
  const nextActiveIdSet = new Set(nextActiveIds);
  const activeItems = rankedItems.filter((item) =>
    nextActiveIdSet.has(item.scenario_id),
  );
  const excludedItems = rankedItems.filter(
    (item) => !nextActiveIdSet.has(item.scenario_id),
  );

  return {
    ...recommendation,
    top_scenarios: activeItems.slice(0, 3),
    all_scores: activeItems,
    active_count: activeItems.length,
    excluded_scores: excludedItems,
  };
}

function bubblePos(x: number, y: number) {
  return {
    left: `${((x - 1) / 4) * 88 + 6}%`,
    top: `${100 - (((y - 1) / 4) * 88 + 6)}%`,
  };
}

function compactScenarioText(value?: string | null) {
  const text = (value ?? "")
    .replace(/\s+/g, "")
    .replace(/^[-—:：，。；;、]+/, "")
    .replace(/^是(?=.+)/, "");
  const firstSentence = text.split(/[。；;]/)[0] ?? "";
  const compact = firstSentence || text;
  if (!compact) return "";
  if (compact.length <= MAX_SCENARIO_TEASER_LENGTH) return compact;
  return compact
    .slice(0, MAX_SCENARIO_TEASER_LENGTH)
    .replace(/[，。；;、:：—-]+$/, "");
}

function compactScenarioSummary(summary?: string | null) {
  const text = (summary ?? "").replace(/\s+/g, "");
  if (!text) return "";

  const layoutMatch = text.match(/环节布局[“"]([^”"]+)[”"]，?([^。；;]*)/);
  if (layoutMatch?.[2]) {
    return compactScenarioText(layoutMatch[2]);
  }

  const positioningMatch = text.match(/战略定位[：:]?([^。；;]*)/);
  if (positioningMatch?.[1]) {
    return compactScenarioText(positioningMatch[1]);
  }

  return compactScenarioText(text);
}

function isGenericScenarioTeaser(value?: string | null) {
  const text = (value ?? "").replace(/\s+/g, "");
  if (!text) return false;
  return (
    /^围绕[“"]?/.test(text) ||
    /^在[^，。；;]{1,12}环节[，,](围绕|针对|布局)/.test(text)
  );
}

function getScenarioTeaser(item: ScenarioRecommendationItem) {
  const positioning = compactScenarioText(item.positioning);
  const teaser = positioning && !isGenericScenarioTeaser(item.positioning)
    ? positioning
    : compactScenarioSummary(item.summary) || compactScenarioText(item.name);
  // Keep the complete quoted transformation, without a dangling suffix.
  return teaser.replace(/^(从[“"][^”"]+[”"]到[“"][^”"]+[”"]).*$/, "$1");
}

function getCanvasLabel(item: ScenarioRecommendationItem) {
  return (
    item.canvas_element?.trim() ||
    item.canvas_elements?.trim() ||
    item.category?.trim() ||
    ""
  );
}

function bubbleLabel(name: string) {
  const compact = name.replace(/\s+/g, "");
  // AI + 1-2个中文字 → 保留完整语义不截断
  const aiCompound = compact.match(/^AI[一-龥]{1,2}/i);
  if (aiCompound) {
    return aiCompound[0].replace(/^ai/i, "AI");
  }
  // 首部英文缩写后跟连接词 → 只保留字母
  const leadingLetters = compact.match(/^[A-Za-z]+/);
  if (leadingLetters) {
    const letters = leadingLetters[0].toUpperCase();
    const nextChar = compact.slice(letters.length, letters.length + 1);
    if (["与", "和", "及", "、"].includes(nextChar)) {
      return letters;
    }
  }
  return compact.slice(0, 4);
}

function clampScore(value: number) {
  return Math.max(1, Math.min(5, Number(value.toFixed(1))));
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("auth_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function ScenarioQuadrantView({
  scenarioRecommendation,
  assessmentId,
}: {
  scenarioRecommendation: ScenarioRecommendationResult;
  assessmentId: string;
}) {
  const queryClient = useQueryClient();
  const [recommendation, setRecommendation] =
    useState<ScenarioRecommendationResult>(scenarioRecommendation);
  const [activeScenarios, setActiveScenarios] = useState<EditableScenario[]>(
    buildScenarioBuckets(scenarioRecommendation).active,
  );
  const [excludedScenarios, setExcludedScenarios] = useState<EditableScenario[]>(
    buildScenarioBuckets(scenarioRecommendation).excluded,
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedTopScenarioId, setExpandedTopScenarioId] = useState<string | null>(null);
  const [isChoosingTop3, setIsChoosingTop3] = useState(false);
  const [top3DraftIds, setTop3DraftIds] = useState<string[]>(
    scenarioRecommendation.top_scenarios.map((item) => item.scenario_id),
  );
  const [top3SaveStatus, setTop3SaveStatus] = useState<SaveStatus>("idle");
  const [calibrationSaveStatus, setCalibrationSaveStatus] =
    useState<SaveStatus>("idle");
  const [poolSaveStatus, setPoolSaveStatus] = useState<SaveStatus>("idle");
  const [hasUnsavedCalibrationChanges, setHasUnsavedCalibrationChanges] =
    useState(false);
  const [pendingPoolScenarioId, setPendingPoolScenarioId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    const nextBuckets = buildScenarioBuckets(scenarioRecommendation);
    setRecommendation(scenarioRecommendation);
    setTop3DraftIds(scenarioRecommendation.top_scenarios.map((item) => item.scenario_id));
    setTop3SaveStatus("idle");
    setActiveScenarios(nextBuckets.active);
    setExcludedScenarios(nextBuckets.excluded);
    setCalibrationSaveStatus("idle");
    setPoolSaveStatus("idle");
    setHasUnsavedCalibrationChanges(false);
    setSelectedId((current) =>
      (current &&
      nextBuckets.active.some((item) => item.scenario_id === current)
        ? current
        : nextBuckets.active[0]?.scenario_id) ?? null,
    );
  }, [scenarioRecommendation]);

  const selected = useMemo(
    () => activeScenarios.find((item) => item.scenario_id === selectedId) ?? null,
    [activeScenarios, selectedId],
  );

  const top3Ids = useMemo(
    () => new Set(recommendation.top_scenarios.map((item) => item.scenario_id)),
    [recommendation.top_scenarios],
  );

  const top3Cards = useMemo(
    () =>
      recommendation.top_scenarios
        .map((item) =>
          activeScenarios.find((scenario) => scenario.scenario_id === item.scenario_id),
        )
        .filter(Boolean) as EditableScenario[],
    [recommendation.top_scenarios, activeScenarios],
  );
  const rankedScenarios = useMemo(
    () => [...activeScenarios, ...excludedScenarios],
    [activeScenarios, excludedScenarios],
  );

  useEffect(() => {
    setExpandedTopScenarioId((current) => current ?? top3Cards[0]?.scenario_id ?? null);
  }, [top3Cards]);

  const canRemoveMore = activeScenarios.length > 3;
  const poolLocked =
    calibrationSaveStatus === "saving" ||
    hasUnsavedCalibrationChanges ||
    poolSaveStatus === "saving" ||
    top3SaveStatus === "saving";

  const refreshScenarioQueries = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: assessmentKeys.detail(assessmentId) }),
      queryClient.invalidateQueries({
        queryKey: assessmentKeys.scenarios(assessmentId),
      }),
      queryClient.invalidateQueries({
        queryKey: assessmentKeys.competitiveness(assessmentId),
      }),
      queryClient.invalidateQueries({
        queryKey: assessmentKeys.endgame(assessmentId),
      }),
    ]);
  }, [assessmentId, queryClient]);

  const applyScenarioRecommendation = useCallback(
    (
      nextRecommendation: ScenarioRecommendationResult,
      preferredSelectedId?: string | null,
    ) => {
      const nextBuckets = buildScenarioBuckets(nextRecommendation);
      setRecommendation(nextRecommendation);
      setTop3DraftIds(nextRecommendation.top_scenarios.map((item) => item.scenario_id));
      setActiveScenarios(nextBuckets.active);
      setExcludedScenarios(nextBuckets.excluded);
      setSelectedId((current) =>
        [preferredSelectedId, current]
          .filter((value): value is string => Boolean(value))
          .find((value) =>
            nextBuckets.active.some((item) => item.scenario_id === value),
          ) ?? nextBuckets.active[0]?.scenario_id ?? null,
      );
    },
    [],
  );

  const handleScoreChange = useCallback(
    (axis: "x" | "y", value: number) => {
      if (!selectedId) return;
      const nextValue = clampScore(value);
      setHasUnsavedCalibrationChanges(true);
      setCalibrationSaveStatus("idle");
      setPoolSaveStatus("idle");
      setActiveScenarios((current) =>
        current.map((item) => {
          if (item.scenario_id !== selectedId) return item;
          const nextX = axis === "x" ? nextValue : item._x;
          const nextY = axis === "y" ? nextValue : item._y;
          const { qs, lps, lpsDisplay, quadrant, tier, level } = recompute(
            nextX,
            nextY,
            item._kappa,
          );

          return {
            ...item,
            _x: nextX,
            _y: nextY,
            _qs: qs,
            _lps: lps,
            _lpsDisplay: lpsDisplay,
            _quadrant: quadrant,
            _tier: tier,
            _level: level,
            priority_structuredness_x: nextX,
            priority_complexity_y: nextY,
            priority_qs: qs,
            priority_lps: lps,
            priority_lps_display: lpsDisplay,
            priority_quadrant: quadrant,
            priority_tier: tier,
            recommendation_level: level,
          };
        }),
      );
    },
    [selectedId],
  );

  const adjustScore = useCallback(
    (axis: "x" | "y", delta: number) => {
      if (!selected) return;
      const currentValue = axis === "x" ? selected._x : selected._y;
      handleScoreChange(axis, currentValue + delta);
    },
    [handleScoreChange, selected],
  );

  const persistScenarioPool = useCallback(
    async (nextActiveIds: string[], scenarioId: string, actionLabel: string) => {
      const previousRecommendation = recommendation;
      const previousSelectedId = selectedId;
      const optimisticRecommendation = buildOptimisticScenarioRecommendation(
        recommendation,
        rankedScenarios,
        nextActiveIds,
      );

      applyScenarioRecommendation(optimisticRecommendation, selectedId);
      setPoolSaveStatus("saving");
      setPendingPoolScenarioId(scenarioId);
      try {
        const response = await updateScenarioPool(assessmentId, {
          active_scenario_ids: nextActiveIds,
        });
        applyScenarioRecommendation(response.scenario_recommendation, selectedId);
        setPoolSaveStatus("saved");
        void refreshScenarioQueries();
      } catch (error) {
        applyScenarioRecommendation(previousRecommendation, previousSelectedId);
        setPoolSaveStatus("error");
        toast({
          title: `${actionLabel}失败`,
          description: formatMutationError(error, "场景池调整"),
          variant: "destructive",
        });
      } finally {
        setPendingPoolScenarioId(null);
      }
    },
    [
      applyScenarioRecommendation,
      assessmentId,
      rankedScenarios,
      recommendation,
      refreshScenarioQueries,
      selectedId,
    ],
  );

  const handleSaveCalibration = useCallback(async () => {
    setCalibrationSaveStatus("saving");
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders(),
      };
      const response = await fetch(
        `${apiBaseUrl}/api/assessments/${assessmentId}/scenarios/calibrations`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            calibrations: activeScenarios.map((item) => ({
              scenario_id: item.scenario_id,
              priority_structuredness_x: item._x,
              priority_complexity_y: item._y,
            })),
          }),
        },
      );
      if (!response.ok) {
        throw new Error(await response.text());
      }

      const payload = (await response.json()) as {
        scenario_recommendation: ScenarioRecommendationResult;
      };
      applyScenarioRecommendation(payload.scenario_recommendation, selectedId);
      setHasUnsavedCalibrationChanges(false);
      setCalibrationSaveStatus("saved");
      void refreshScenarioQueries();
    } catch (error) {
      setCalibrationSaveStatus("error");
      toast({
        title: "保存校准失败",
        description: formatMutationError(error, "场景校准"),
        variant: "destructive",
      });
    }
  }, [
    activeScenarios,
    applyScenarioRecommendation,
    assessmentId,
    refreshScenarioQueries,
    selectedId,
  ]);

  const handleRemoveScenario = useCallback(
    async (scenarioId: string) => {
      if (!canRemoveMore || poolLocked) return;
      const nextActiveIds = activeScenarios
        .filter((item) => item.scenario_id !== scenarioId)
        .map((item) => item.scenario_id);
      await persistScenarioPool(nextActiveIds, scenarioId, "移出场景");
    },
    [activeScenarios, canRemoveMore, persistScenarioPool, poolLocked],
  );

  const handleRestoreScenario = useCallback(
    async (scenarioId: string) => {
      if (poolLocked) return;
      const nextActiveIds = [
        ...activeScenarios.map((item) => item.scenario_id),
        scenarioId,
      ];
      await persistScenarioPool(nextActiveIds, scenarioId, "加回场景");
    },
    [activeScenarios, persistScenarioPool, poolLocked],
  );

  const handleToggleTopScenario = useCallback(
    (scenarioId: string) => {
      setExpandedTopScenarioId((current) =>
        current === scenarioId ? null : scenarioId,
      );
    },
    [],
  );

  const handleSaveTop3Selection = useCallback(async () => {
    if (top3DraftIds.length !== 3 || poolLocked) return;
    setTop3SaveStatus("saving");
    try {
      const response = await saveTop3Scenarios(assessmentId, top3DraftIds);
      applyScenarioRecommendation(response.scenario_recommendation);
      setIsChoosingTop3(false);
      setTop3SaveStatus("saved");
      void refreshScenarioQueries();
      toast({ title: "Top 3 应用场景已更新" });
    } catch (error) {
      setTop3SaveStatus("error");
      toast({
        title: "保存场景选择失败",
        description: formatMutationError(error, "Top 3 场景"),
        variant: "destructive",
      });
    }
  }, [assessmentId, top3DraftIds, poolLocked, applyScenarioRecommendation, refreshScenarioQueries]);

  return (
    <div className="space-y-10">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="section-label section-label-normal">步骤1/2：场景池校准</p>
            <h2 className="section-heading">场景池校准与 Top 3 AI 推荐场景</h2>
          </div>
          <span className="badge badge-warning">四象限评分</span>
        </div>
        <p className="mt-3 text-sm leading-7 text-warm-secondary">
          系统根据所选创新方向评估 {recommendation.evaluated_count} 个候选场景。您可以调整候选池中每个场景的 X/Y 评分，
          并对场景进行增删。保存校准或调整场景池会按新评分重新推荐 Top 3，替换当前选择；之后仍可人工重新选择。
        </p>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
        <div className="min-w-0 space-y-4">
          <section className="rounded-2xl border border-warm-border-light bg-warm-surface p-5">
            <h3 className="font-heading text-base font-bold text-warm-text">候选池校准</h3>
            {selected ? (
              <p className="mt-1 text-sm text-warm-accent">当前场景：{selected.name}</p>
            ) : (
              <p className="mt-1 text-sm text-warm-muted">
                请先从下方有效场景池里选择一个场景。
              </p>
            )}

            <div className="my-4 border-t border-warm-border-light" />

            {selected ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <ScoreEditor
                    label="结构化程度 X"
                    value={selected._x}
                    helper="越高越适合沉淀为稳定的 AI 能力"
                    description={X_DESCRIPTIONS[Math.round(selected._x)] ?? ""}
                    onDecrease={() => adjustScore("x", -0.1)}
                    onIncrease={() => adjustScore("x", 0.1)}
                    onChange={(value) => handleScoreChange("x", value)}
                  />
                  <ScoreEditor
                    label="实施复杂度 Y"
                    value={selected._y}
                    helper="越高代表落地阻力和复杂度越大"
                    description={Y_DESCRIPTIONS[Math.round(selected._y)] ?? ""}
                    onDecrease={() => adjustScore("y", -0.1)}
                    onIncrease={() => adjustScore("y", 0.1)}
                    onChange={(value) => handleScoreChange("y", value)}
                  />
                </div>

                <div className="mt-4 rounded-xl bg-warm-inset px-4 py-3 text-sm">
                  <p className="mb-2 text-xs font-medium text-warm-muted">实时预览</p>
                  <div className="space-y-1.5">
                    <PreviewRow label="QS 象限得分" value={String(selected._qs)} />
                    <p className="text-[11px] leading-5 text-warm-muted">QS = X × Y，用于体现象限位置。</p>
                    <PreviewRow
                      label="LPS 综合优先级"
                      value={`${selected._lpsDisplay} / 10`}
                    />
                    <p className="text-[11px] leading-5 text-warm-muted">LPS = [X × 0.6 + (6 - Y) × 0.4] × 行业系数 × 2，用于推荐排序。</p>
                    <PreviewRow label="所属象限" value={selected._quadrant} />
                    <PreviewRow label="推荐级别" value={selected._level} />
                  </div>
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleSaveCalibration}
                    disabled={
                      calibrationSaveStatus === "saving" ||
                      poolSaveStatus === "saving" ||
                      !hasUnsavedCalibrationChanges
                    }
                    className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                      calibrationSaveStatus === "saving"
                        ? "cursor-wait bg-warm-inset text-warm-muted"
                        : calibrationSaveStatus === "saved"
                          ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                          : hasUnsavedCalibrationChanges
                            ? "bg-amber-500 text-white hover:bg-amber-600"
                            : "cursor-not-allowed bg-warm-inset text-warm-muted"
                    }`}
                  >
                    {calibrationSaveStatus === "saving"
                      ? "保存中..."
                      : calibrationSaveStatus === "saved"
                        ? "已保存"
                        : calibrationSaveStatus === "error"
                          ? "保存失败，请重试"
                          : "保存校准并重新推荐"}
                  </button>
                  <span className="text-[11px] text-warm-muted">
                    {hasUnsavedCalibrationChanges
                      ? "保存后，后续竞争力、终局和综合报告会自动失效。"
                      : "场景增减前请先保存当前校准，避免本地未保存改动被覆盖。"}
                  </span>
                </div>
              </>
            ) : (
              <p className="py-4 text-center text-sm text-warm-muted">
                选择有效场景池中的任一场景后，可以在这里通过 +/- 或滑块调整评分。
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-warm-border-light bg-warm-surface p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-heading text-base font-bold text-warm-text">有效场景池</h3>
              <span className="rounded-full bg-warm-inset px-2.5 py-0.5 text-xs text-warm-muted">
                总 {recommendation.evaluated_count}
              </span>
            </div>
            <p className="mt-2 text-xs leading-6 text-warm-muted">
              这里的场景会参与 Top 3 排序和后续报告生成。至少保留 3 个场景。
            </p>
            <div className="my-4 border-t border-warm-border-light" />

            <div className="max-h-[440px] space-y-2 overflow-y-auto pr-2">
              {activeScenarios.map((item) => {
                const isSelected = selectedId === item.scenario_id;
                const meta = QUADRANT_META[item._quadrant];
                const isPending = pendingPoolScenarioId === item.scenario_id;
                return (
                  <div
                    key={item.scenario_id}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                      isSelected
                        ? `${meta.borderClass} bg-white shadow-sm`
                        : "border-warm-border-light bg-white hover:border-warm-accent/30"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedId((current) =>
                              current === item.scenario_id ? null : item.scenario_id,
                            )
                          }
                          className="w-full text-left"
                        >
                          <p className="truncate text-sm font-semibold text-warm-text">
                            {item.name}
                          </p>
                        </button>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className={`badge shrink-0 text-[0.6rem] ${meta.badgeClass}`}>
                          {item._quadrant}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveScenario(item.scenario_id)}
                          disabled={!canRemoveMore || poolLocked || isPending}
                          className={`rounded-full border px-3 py-1 text-[0.7rem] font-medium transition ${
                            !canRemoveMore || poolLocked || isPending
                              ? "cursor-not-allowed border-warm-border-light bg-warm-inset text-warm-muted"
                              : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                          }`}
                        >
                          {isPending && poolSaveStatus === "saving" ? "移出中..." : "移出"}
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-warm-muted">
                      <span>X: {item._x}</span>
                      <span>Y: {item._y}</span>
                      <span className="font-medium text-warm-text">{item._lpsDisplay} 分</span>
                      <span>{item._level}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {excludedScenarios.length > 0 ? (
            <section className="rounded-2xl border border-warm-border-light bg-warm-surface p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-heading text-base font-bold text-warm-text">已移出场景</h3>
                <span className="rounded-full bg-warm-inset px-2.5 py-0.5 text-xs text-warm-muted">
                  {excludedScenarios.length} 个场景
                </span>
              </div>
              <p className="mt-2 text-xs leading-6 text-warm-muted">
                已移出的场景不会参与 Top 3、竞争力或终局生成；需要时可以加回有效场景池。
              </p>
              <div className="my-4 border-t border-warm-border-light" />

              <div className="max-h-[320px] space-y-2 overflow-y-auto pr-2">
                {excludedScenarios.map((item) => {
                  const meta = QUADRANT_META[item._quadrant];
                  const isPending = pendingPoolScenarioId === item.scenario_id;
                  return (
                    <div
                      key={item.scenario_id}
                      className="rounded-xl border border-warm-border-light bg-white px-4 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold text-warm-text">
                            {item.name}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className={`badge shrink-0 text-[0.6rem] ${meta.badgeClass}`}>
                            {item._quadrant}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleRestoreScenario(item.scenario_id)}
                            disabled={poolLocked || isPending}
                            className={`rounded-full border px-3 py-1 text-[0.7rem] font-medium transition ${
                              poolLocked || isPending
                                ? "cursor-not-allowed border-warm-border-light bg-warm-inset text-warm-muted"
                                : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            }`}
                          >
                            {isPending && poolSaveStatus === "saving" ? "加回中..." : "加回"}
                          </button>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-warm-muted">
                        <span>X: {item._x}</span>
                        <span>Y: {item._y}</span>
                        <span className="font-medium text-warm-text">{item._lpsDisplay} 分</span>
                        <span>{item._level}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}
        </div>

        <div className="min-w-0">
          <div className="card-inset">
            <div className="mb-4 rounded-xl border border-warm-border-light bg-white px-4 py-4 text-xs text-warm-muted">
              <p className="font-medium text-warm-text">评分解释</p>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <p>X 轴：结构化程度，越高表示越适合沉淀为标准 AI 能力。</p>
                <p>Y 轴：实施复杂度，越低越适合优先启动。</p>
              </div>
            </div>

            <div className="mb-4 flex flex-wrap gap-3 text-xs text-warm-muted">
              <span>金色外圈表示当前 Top 3</span>
              <span>图中只显示当前有效场景池；点击气泡或左侧卡片可查看并校准</span>
            </div>

            <div className="relative w-full" style={{ paddingBottom: "min(100%, 560px)" }}>
              <div className="absolute inset-0 overflow-hidden rounded-xl border border-warm-border-light bg-warm-inset">
                <div className="absolute inset-0 flex">
                  <div className="flex flex-1 flex-col">
                    <div className="flex flex-1">
                      <div className={`flex flex-1 items-center justify-center ${QUADRANT_META["人机协作区"].areaClass}`}>
                        <span className={`text-[0.65rem] font-medium ${QUADRANT_META["人机协作区"].areaLabelClass}`}>
                          人机协作区
                        </span>
                      </div>
                      <div className={`flex flex-1 items-center justify-center ${QUADRANT_META["AI优先区"].areaClass}`}>
                        <span className={`text-[0.65rem] font-medium ${QUADRANT_META["AI优先区"].areaLabelClass}`}>
                          AI优先区
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-1">
                      <div className={`flex flex-1 items-center justify-center ${QUADRANT_META["人类保留区"].areaClass}`}>
                        <span className={`text-[0.65rem] font-medium ${QUADRANT_META["人类保留区"].areaLabelClass}`}>
                          人类保留区
                        </span>
                      </div>
                      <div className={`flex flex-1 items-center justify-center ${QUADRANT_META["自动化主战场"].areaClass}`}>
                        <span className={`text-[0.65rem] font-medium ${QUADRANT_META["自动化主战场"].areaLabelClass}`}>
                          自动化主战场
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="absolute bg-warm-border-light/70" style={{ left: "50%", top: 0, bottom: 0, width: 1 }} />
                <div className="absolute bg-warm-border-light/70" style={{ top: "50%", left: 0, right: 0, height: 1 }} />

                <div className="absolute bottom-1 left-1/2 -translate-x-1/2 text-[0.65rem] text-warm-muted">
                  结构化程度 →
                </div>
                <div
                  className="absolute left-1 top-1/2 -translate-y-1/2 text-[0.65rem] text-warm-muted"
                  style={{ writingMode: "vertical-rl" }}
                >
                  实施复杂度 →
                </div>

                {activeScenarios.map((item) => {
                  const position = bubblePos(item._x, item._y);
                  const meta = QUADRANT_META[item._quadrant];
                  const isTop3 = top3Ids.has(item.scenario_id);
                  const isSelected = item.scenario_id === selectedId;
                  return (
                    <button
                      key={item.scenario_id}
                      type="button"
                      title={`${item.name}\nX:${item._x} Y:${item._y} LPS:${item._lpsDisplay}`}
                      onClick={() =>
                        setSelectedId((current) =>
                          current === item.scenario_id ? null : item.scenario_id,
                        )
                      }
                      className="absolute flex items-center justify-center -translate-x-1/2 -translate-y-1/2 rounded-full px-1 text-center text-[0.62rem] font-bold leading-tight text-white transition break-all"
                      style={{
                        left: position.left,
                        top: position.top,
                        width: isTop3 ? "3.3rem" : "3rem",
                        height: isTop3 ? "3.3rem" : "3rem",
                        backgroundColor: meta.bubbleColor,
                        boxShadow: isSelected
                          ? "0 0 0 3px rgba(255,255,255,0.9), 0 0 0 5px rgba(245,158,11,0.5)"
                          : isTop3
                            ? "0 0 0 2px rgba(245,158,11,0.7)"
                            : "0 4px 12px rgba(45,34,24,0.15)",
                        zIndex: isSelected ? 12 : isTop3 ? 10 : 5,
                      }}
                    >
                      {bubbleLabel(item.name)}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      <section className="mx-auto w-full max-w-[1440px]">
        <p className="section-label section-label-normal">步骤2/2：Top3 AI 应用场景推荐</p>
        <h2 className="section-heading">Top 3 AI 应用场景推荐</h2>
        <p className="mt-2 text-sm leading-7 text-warm-secondary">
          基于您所选的创新方向与场景池校准结果，筛选出以下 3 个最具战略价值与落地可行性的场景。
          点击任意场景卡片，查看战略价值、预期收益、资源准备的完整分析。
        </p>

        <div className="mt-4 rounded-xl border border-warm-border-light bg-white p-4">
          <button
            type="button"
            className="btn-secondary text-xs"
            disabled={poolLocked}
            aria-expanded={isChoosingTop3}
            onClick={() => {
              setTop3DraftIds(recommendation.top_scenarios.map((item) => item.scenario_id));
              setIsChoosingTop3((current) => !current);
            }}
          >
            {isChoosingTop3 ? "取消调整" : "重新选择 Top 3 应用场景"}
          </button>
          {isChoosingTop3 && (
            <div className="mt-3 space-y-3">
              <p className="text-xs text-warm-muted">
                从有效场景池自由选择 3 项，保存后将替换系统推荐；已有的后续分析需重新生成。
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {activeScenarios.map((item) => {
                  const checked = top3DraftIds.includes(item.scenario_id);
                  return (
                    <label key={item.scenario_id} className="flex cursor-pointer items-center gap-2 rounded-lg border border-warm-border-light p-2 text-sm">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={poolLocked || (!checked && top3DraftIds.length >= 3)}
                        onChange={() => setTop3DraftIds((current) =>
                          checked
                            ? current.filter((id) => id !== item.scenario_id)
                            : [...current, item.scenario_id]
                        )}
                      />
                      <span>{item.name}</span>
                    </label>
                  );
                })}
              </div>
              <button
                type="button"
                className="btn-primary text-xs"
                disabled={poolLocked || top3DraftIds.length !== 3}
                onClick={handleSaveTop3Selection}
              >
                {top3SaveStatus === "saving"
                  ? "保存中..."
                  : `确认新的 Top 3（已选 ${top3DraftIds.length}/3）`}
              </button>
            </div>
          )}
        </div>

        <div className="mt-5 flex flex-col gap-3.5">
          {top3Cards.map((item, index) => {
            const isOpen = expandedTopScenarioId === item.scenario_id;
            const meta = QUADRANT_META[item._quadrant];
            const positioningText = getScenarioTeaser(item);
            const canvasTag = getCanvasLabel(item);
            // 三段式内容：新字段优先，旧字段 fallback
            const valueContent = item.value_text || item.canvas_elements || "";
            const hasBenefits = item.benefits && item.benefits.length > 0;
            const hasResources = item.resources && item.resources.length > 0;
            const benefitLines = hasBenefits
              ? item.benefits!.map((b) => `· ${b.text} (→ ${b.canvas})`).join("\n")
              : "";
            const resourceLines = hasResources
              ? item.resources!.map((r) => `· ${r.label}：${r.text}`).join("\n")
              : "";

            return (
              <div
                key={item.scenario_id}
                className={`rounded-xl border bg-white overflow-hidden transition ${
                  isOpen
                    ? "border-emerald-300 shadow-md"
                    : "border-warm-border-light hover:border-emerald-200 hover:shadow-sm"
                }`}
              >
                <div className={`h-1 ${RANK_ACCENT_BG[index] ?? "bg-warm-border-light"}`} />

                <button
                  type="button"
                  onClick={() => handleToggleTopScenario(item.scenario_id)}
                  className={`flex items-center gap-4 px-6 py-5 w-full text-left transition ${
                    isOpen ? "bg-emerald-50/60" : "hover:bg-warm-inset"
                  }`}
                >
                  <span className="text-2xl shrink-0">{RANK_EMOJI[index]}</span>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-base font-bold text-warm-text sm:text-xl">
                        场景{SCENE_ORDINAL[index]} · {item.name}
                      </span>
                      {canvasTag ? (
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
                          {canvasTag}
                        </span>
                      ) : null}
                    </div>
                    <p
                      className={`mt-1 text-sm leading-relaxed ${
                        isOpen
                          ? "font-semibold text-emerald-800"
                          : "italic text-warm-muted"
                      }`}
                    >
                      {positioningText || "暂无战略定位描述"}
                    </p>
                  </div>

                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className="text-[10px] text-warm-muted">
                      {isOpen ? "点击收起" : "点击展开"}
                    </span>
                    <span
                      className={`text-xs text-warm-muted transition-transform duration-200 ${
                        isOpen ? "rotate-180 text-emerald-600" : ""
                      }`}
                    >
                      ▼
                    </span>
                  </div>
                </button>

                {isOpen ? (
                  <div className="border-t border-warm-border-light">
                    <div className="grid grid-cols-1 sm:grid-cols-3">
                      <TopScenarioSection
                        idx="①"
                        title="战略价值"
                        subtitle="为什么值得做"
                        content={valueContent}
                        valueDimensions={item.value_dimensions}
                        accent="emerald"
                      />
                      <TopScenarioSection
                        idx="②"
                        title="预期收益"
                        subtitle="做了能得到什么"
                        content={hasBenefits ? benefitLines : (item.expected_effects || "")}
                        accent="amber"
                      />
                      <TopScenarioSection
                        idx="③"
                        title="资源准备"
                        subtitle="现在做需要什么"
                        content={hasResources ? resourceLines : (item.core_data_requirements || "")}
                        accent="slate"
                      />
                    </div>

                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-warm-muted">{label}</span>
      <span className="font-semibold text-warm-text">{value}</span>
    </div>
  );
}

function ScoreEditor({
  label,
  value,
  helper,
  description,
  onDecrease,
  onIncrease,
  onChange,
}: {
  label: string;
  value: number;
  helper: string;
  description: string;
  onDecrease: () => void;
  onIncrease: () => void;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-warm-secondary">{label}</span>
        <span className="font-bold text-warm-text">{value}</span>
      </div>
      <p className="mb-2 text-[0.7rem] text-warm-muted">{helper}</p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDecrease}
          aria-label={`${label} 减少`}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-warm-border-light bg-white text-sm text-warm-text transition hover:border-warm-accent"
        >
          -
        </button>
        <input
          type="range"
          min="1"
          max="5"
          step="0.1"
          value={value}
          onChange={(event) => onChange(parseFloat(event.target.value))}
          className="w-full accent-amber-600"
        />
        <button
          type="button"
          onClick={onIncrease}
          aria-label={`${label} 增加`}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-warm-border-light bg-white text-sm text-warm-text transition hover:border-warm-accent"
        >
          +
        </button>
      </div>
      <div className="mt-1 flex justify-between text-[0.65rem] text-warm-muted">
        <span>1</span>
        <span>5</span>
      </div>
      <p className="mt-2 text-[0.7rem] leading-relaxed text-warm-muted">{description}</p>
    </div>
  );
}

function TopScenarioSection({
  idx,
  title,
  subtitle,
  content,
  valueDimensions,
  accent,
}: {
  idx: string;
  title: string;
  subtitle: string;
  content?: string | null;
  valueDimensions?: string[] | null;
  accent: "emerald" | "amber" | "slate";
}) {
  const numBg: Record<string, string> = {
    emerald: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-600",
    slate: "bg-warm-inset text-warm-text",
  };

  const dimColors: Record<string, string> = {
    "竞争格局": "bg-rose-50 text-rose-700",
    "行业趋势": "bg-sky-50 text-sky-700",
    "自身禀赋": "bg-violet-50 text-violet-700",
  };

  const hasDimensions = valueDimensions && valueDimensions.length > 0;

  return (
    <div className="px-6 py-6 [&:not(:last-child)]:border-b sm:[&:not(:last-child)]:border-b-0 sm:[&:not(:last-child)]:border-r border-warm-border-light">
      <div className="mb-4 flex items-center gap-2">
        <span
          className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${numBg[accent] ?? numBg.slate}`}
        >
          {idx}
        </span>
        <div>
          <p className="text-sm font-bold text-warm-text">
            {title}
          </p>
          <p className="text-xs text-warm-muted">{subtitle}</p>
        </div>
      </div>
      {hasDimensions ? (
        <div className="mb-3 flex flex-wrap gap-2">
          {valueDimensions!.map((d) => (
            <span
              key={d}
              className={`inline-flex items-center rounded-md px-2.5 py-1 text-xs font-semibold ${
                dimColors[d] ?? "bg-warm-inset text-warm-muted"
              }`}
            >
              {d}
            </span>
          ))}
        </div>
      ) : null}
      <p className="whitespace-pre-line text-sm leading-8 text-warm-text">
        {content || "待补充"}
      </p>
    </div>
  );
}

function DetailCard({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-xl bg-warm-inset px-4 py-3">
      <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">{title}</p>
      <p className="mt-1 text-sm leading-7 text-warm-secondary">{content}</p>
    </div>
  );
}
