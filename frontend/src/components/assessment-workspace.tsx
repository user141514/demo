"use client";

import React from "react";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { AssessmentFormSection } from "@/components/assessment-form-section";
import { IntakeImportSection } from "@/components/intake-import-section";
import { AssessmentSkeleton } from "@/components/assessment-skeleton";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ActionBtn,
  type WorkflowModule,
} from "@/components/workflow-sidebar";
import {
  applyAssessmentDetailToStore,
  computeProgress,
  countPrefillFields,
  createInitialAssessmentForm,
  initialForm,
  initialProgress,
  mapAssessmentToForm,
  mergePrefillIntoForm,
} from "@/lib/assessment-utils";
import {
  buildAssessmentWorkflowState,
  type WorkflowDisplayState,
} from "@/lib/assessment-workflow-state";
import {
  getCompetitivenessResultPath,
  getResultsDashboardPath,
  getScenarioResultPath,
} from "@/lib/assessment-result-routes";
import {
  isPaidWorkflowKey,
  isPaymentRequired,
} from "@/lib/payment-entitlement";
import { ApiError, formatMutationError } from "@/lib/api";
import type { AssessmentCreateRequest, AssessmentProgress } from "@/lib/types";
import {
  assessmentKeys,
  useAssessmentDetail,
  useExpandDirections,
  useGenerateCanvas,
  useGenerateCompetitiveness,
  useGenerateEndgame,
  useGenerateProfile,
  useGenerateScenarios,
  useIntakeSession,
  useSelectDirections,
} from "@/hooks";
import { toast } from "@/hooks/use-toast";
import { useAssessmentStore } from "@/stores/assessment-store";

const SLOW_HINT_DELAY_MS = 5000;

function withSlowHint<T>(
  promise: Promise<T>,
  title: string,
  showToast: (msg: { title: string; description: string }) => void,
): Promise<T> {
  const timer = setTimeout(() => {
    showToast({
      title: "请稍候",
      description: `${title}，正在进行 AI 分析。预计 1–2 分钟，实际时间取决于资料量与网络状况，请稍候。`,
    });
  }, SLOW_HINT_DELAY_MS);

  return promise.finally(() => clearTimeout(timer));
}

type ResultCardItem = {
  key: string;
  label: string;
  state: WorkflowDisplayState;
  done: boolean;
  statusLabel: string;
  link?: string;
  paymentLocked?: boolean;
};

/**
 * 承载评估工作台主流程、状态卡和结果入口。
 */
export function AssessmentWorkspace({
  assessmentId,
  prefillSessionId,
  companyName,
}: {
  assessmentId?: string;
  prefillSessionId?: string;
  companyName?: string;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const store = useAssessmentStore();

  const [form, setForm] = useState<AssessmentCreateRequest>(() =>
    createInitialAssessmentForm({ assessmentId, prefillSessionId, companyName }),
  );
  const [prefillSummary, setPrefillSummary] = useState<{
    importSessionId: string;
    mappedCount: number;
  } | null>(null);
  const [prefillError, setPrefillError] = useState<string | null>(null);
  const [appliedPrefillSessionId, setAppliedPrefillSessionId] = useState<
    string | null
  >(null);
  const [progress, setProgress] = useState<AssessmentProgress>(initialProgress);
  const [showImport, setShowImport] = useState(false);
  const [isQuestionnaireExpanded, setIsQuestionnaireExpanded] = useState(true);
  const [localPrefillSessionId, setLocalPrefillSessionId] = useState<
    string | null
  >(null);
  const [isPaymentDialogOpen, setIsPaymentDialogOpen] = useState(false);

  const effectivePrefillSessionId =
    !assessmentId
      ? (localPrefillSessionId ?? prefillSessionId ?? null)
      : null;

  const detailQuery = useAssessmentDetail(assessmentId);
  const prefillQuery = useIntakeSession(effectivePrefillSessionId);

  const generateProfile = useGenerateProfile();
  const generateCanvas = useGenerateCanvas();
  const expandDirections = useExpandDirections();
  const selectDirections = useSelectDirections();
  const generateScenarios = useGenerateScenarios();
  const generateCompetitiveness = useGenerateCompetitiveness();
  const generateEndgame = useGenerateEndgame();

  useEffect(() => {
    if (!detailQuery.data) return;

    applyAssessmentDetailToStore(detailQuery.data, store);
    setForm(mapAssessmentToForm(detailQuery.data.assessment));
    setProgress(detailQuery.data.progress);
    // store actions are stable Zustand references — including the store object
    // itself in deps would cause an infinite loop because useAssessmentStore()
    // returns a new merged object on every state change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailQuery.data]);

  useEffect(() => {
    if (
      assessmentId ||
      !prefillQuery.data ||
      appliedPrefillSessionId === prefillQuery.data.import_session_id
    ) {
      return;
    }

    setForm((current) =>
      mergePrefillIntoForm(current, prefillQuery.data.assessment_prefill),
    );
    setPrefillSummary({
      importSessionId: prefillQuery.data.import_session_id,
      mappedCount: countPrefillFields(prefillQuery.data.assessment_prefill),
    });
    setAppliedPrefillSessionId(prefillQuery.data.import_session_id);
  }, [appliedPrefillSessionId, assessmentId, prefillQuery.data]);

  const updateField = useCallback(
    (key: keyof AssessmentCreateRequest, value: string) => {
      setForm((current) => ({ ...current, [key]: value }));
    },
    [],
  );

  const handleResetForm = useCallback(() => {
    if (assessmentId) {
      router.push("/assessment");
      return;
    }

    setForm(initialForm);
    store.resetAll();
    setProgress(initialProgress);
    setPrefillSummary(null);
    setPrefillError(null);
  }, [assessmentId, router, store]);

  const handleGenerateProfile = useCallback(async () => {
    if (!store.assessment) return;

    try {
      store.setDirectionSelection(null);
      store.setSelectedDirectionIds([]);
      const result = await withSlowHint(
        generateProfile.mutateAsync(store.assessment.id),
        "正在生成企业画像",
        toast,
      );

      store.setAssessment(result.assessment);
      store.setCompanyProfile(result.profile);
      store.setProfileMode(result.generation_mode);
      store.resetDownstream("profile");
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: true,
          hasCanvas: false,
          hasBreakthrough: false,
          hasDirections: false,
          hasCompetitiveness: false,
          hasEndgame: false,
          hasScenarios: false,
          hasReport: false,
        }),
      );
      toast({
        title: "企业画像已生成",
        description: `模式：${result.generation_mode}`,
      });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "企业画像生成"),
        variant: "destructive",
      });
    }
  }, [generateProfile, store]);

  const handleGenerateCanvas = useCallback(async () => {
    if (!store.assessment) return;

    try {
      const result = await withSlowHint(
        generateCanvas.mutateAsync(store.assessment.id),
        "正在生成商业画布 9 格诊断",
        toast,
      );

      store.setAssessment(result.assessment);
      store.setCanvasDiagnosis(result.canvas_diagnosis);
      store.resetDownstream("canvas");
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: true,
          hasCanvas: true,
          hasBreakthrough: false,
          hasDirections: false,
          hasCompetitiveness: false,
          hasEndgame: false,
          hasScenarios: false,
          hasReport: false,
        }),
      );
      toast({
        title: "商业画布已生成",
        description: "可查看薄弱模块与建议优先动作。",
      });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "商业画布生成"),
        variant: "destructive",
      });
    }
  }, [generateCanvas, store]);

  const handleGenerateBreakthrough = useCallback(async () => {
    if (!store.assessment) return;
    router.push(`/assessment/${store.assessment.id}/scoring`);
  }, [router, store.assessment]);

  const handleGenerateDirections = useCallback(async () => {
    if (!store.assessment) return;

    try {
      const result = await withSlowHint(
        expandDirections.mutateAsync(store.assessment.id),
        "正在延展创新方向",
        toast,
      );

      store.resetDownstream("directions");
      store.setDirectionData(result);
      store.setDirectionSelection(result.direction_selection);
      store.setSelectedDirectionIds(
        result.direction_selection?.selected_directions.map(
          (direction) => direction.direction_id,
        ) ?? [],
      );
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: progress.has_profile,
          hasCanvas: progress.has_canvas,
          hasBreakthrough: progress.has_breakthrough,
          hasDirections: false,
          hasCompetitiveness: false,
          hasEndgame: false,
          hasScenarios: false,
          hasReport: false,
        }),
      );
      toast({ title: "创新方向延展已生成" });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
      router.push(`/assessment/${store.assessment.id}/directions`);
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "创新方向延展生成"),
        variant: "destructive",
      });
    }
  }, [expandDirections, router, store]);

  const handleSelectDirections = useCallback(async () => {
    if (!store.assessment || store.selectedDirectionIds.length < 1) return;

    try {
      const result = await selectDirections.mutateAsync({
        assessmentId: store.assessment.id,
        payload: { selected_direction_ids: store.selectedDirectionIds },
      });

      store.setDirectionSelection(result);
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: progress.has_profile,
          hasCanvas: progress.has_canvas,
          hasBreakthrough: progress.has_breakthrough,
          hasDirections: true,
          hasCompetitiveness: false,
          hasEndgame: false,
          hasScenarios: false,
          hasReport: false,
        }),
      );
      toast({ title: "创新方向已确认" });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "保存失败",
        description: formatMutationError(error, "创新方向保存"),
        variant: "destructive",
      });
    }
  }, [selectDirections, store]);

  const handleGenerateScenarios = useCallback(async () => {
    if (!store.assessment) return;

    try {
      const result = await withSlowHint(
        generateScenarios.mutateAsync(store.assessment.id),
        "正在生成 Top 3 AI 场景推荐",
        toast,
      );

      store.resetDownstream("scenarios");
      store.setAssessment(result.assessment);
      store.setScenarioRecommendation(result.scenario_recommendation);
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: progress.has_profile,
          hasCanvas: progress.has_canvas,
          hasBreakthrough: progress.has_breakthrough,
          hasDirections: progress.has_directions,
          hasCompetitiveness: false,
          hasEndgame: false,
          hasScenarios: true,
          hasReport: false,
        }),
      );
      toast({ title: "场景推荐已生成" });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "场景推荐生成"),
        variant: "destructive",
      });
    }
  }, [generateScenarios, store]);

  const handleGenerateCompetitiveness = useCallback(async () => {
    if (!store.assessment) return;

    try {
      const result = await withSlowHint(
        generateCompetitiveness.mutateAsync(store.assessment.id),
        "正在分析差异化竞争力",
        toast,
      );

      store.resetDownstream("competitiveness");
      store.setCompetitivenessData(result);
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: progress.has_profile,
          hasCanvas: progress.has_canvas,
          hasBreakthrough: progress.has_breakthrough,
          hasDirections: progress.has_directions,
          hasCompetitiveness: true,
          hasEndgame: false,
          hasScenarios: progress.has_scenarios,
          hasReport: false,
        }),
      );
      toast({ title: "差异化竞争力分析已生成" });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "差异化竞争力分析生成"),
        variant: "destructive",
      });
    }
  }, [generateCompetitiveness, store]);

  const handleGenerateEndgame = useCallback(async () => {
    if (!store.assessment) return;

    try {
      const result = await withSlowHint(
        generateEndgame.mutateAsync(store.assessment.id),
        "正在生成核心竞争力推进策略",
        toast,
      );

      store.setEndgameData(result);
      setProgress((prev) =>
        computeProgress({
          hasAssessment: true,
          hasProfile: progress.has_profile,
          hasCanvas: progress.has_canvas,
          hasBreakthrough: progress.has_breakthrough,
          hasDirections: progress.has_directions,
          hasCompetitiveness: progress.has_competitiveness,
          hasEndgame: true,
          hasScenarios: progress.has_scenarios,
          hasReport: false,
        }),
      );
      toast({ title: "核心竞争力推进策略已生成" });
      new BroadcastChannel("ai-chat-context").postMessage({
        type: "context-updated",
        assessmentId: store.assessment!.id,
      });
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "核心竞争力推进策略生成"),
        variant: "destructive",
      });
    }
  }, [generateEndgame, store]);

  const currentAssessment = store.assessment ?? null;
  const entitlement = detailQuery.data?.entitlement ?? null;
  const requiresPayment = isPaymentRequired(entitlement);

  const handleOpenPaymentDialog = useCallback(() => {
    setIsPaymentDialogOpen(true);
  }, []);

  const handlePaymentUnlocked = useCallback(async () => {
    setIsPaymentDialogOpen(false);
    if (!currentAssessment?.id) return;
    await queryClient.invalidateQueries({
      queryKey: assessmentKeys.detail(currentAssessment.id),
    });
    await detailQuery.refetch();
  }, [currentAssessment?.id, detailQuery, queryClient]);

  useEffect(() => {
    if (currentAssessment) {
      setIsQuestionnaireExpanded(false);
    }
  }, [currentAssessment]);

  const isMissingAssessment =
    detailQuery.error instanceof ApiError &&
    detailQuery.error.status === 404;

  useEffect(() => {
    if (!isMissingAssessment) {
      return;
    }
    queryClient.invalidateQueries({ queryKey: ["my-assessments"] });
  }, [isMissingAssessment, queryClient]);

  if (detailQuery.isLoading) return <AssessmentSkeleton />;

  if (detailQuery.isError) {
    return (
      <div className="space-y-4 rounded-xl msg-error p-6 text-sm">
        <p>
          {isMissingAssessment
            ? "该评估可能已经被删除，评估历史正在同步。请返回评估历史刷新后再继续。"
            : detailQuery.error instanceof Error
              ? detailQuery.error.message
              : "Assessment 加载失败。"}
        </p>
        <div className="flex flex-wrap gap-3">
          {isMissingAssessment ? (
            <Link href="/history" className="btn-primary text-xs">
              返回评估历史
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => detailQuery.refetch()}
              className="btn-secondary text-xs"
            >
              重试加载
            </button>
          )}
        </div>
      </div>
    );
  }

  const hasProfile = store.companyProfile !== null;
  const hasCanvas = store.canvasDiagnosis !== null;
  const hasBreakthrough =
    progress.has_breakthrough ||
    (store.breakthroughSelection !== null &&
      store.breakthroughSelection.selected_elements.length >= 1);
  const hasDirections =
    progress.has_directions ||
    store.directionData !== null ||
    store.directionSelection !== null;
  const hasCompetitiveness =
    progress.has_competitiveness || store.competitivenessData !== null;
  const hasScenarios = store.scenarioRecommendation !== null;
  const hasEndgame = store.endgameData !== null;
  const hasDashboard =
    progress.has_profile ||
    progress.has_canvas ||
    progress.has_breakthrough ||
    progress.has_directions ||
    progress.has_competitiveness ||
    progress.has_scenarios ||
    hasEndgame;

  const workflowState = buildAssessmentWorkflowState({
    assessmentId: currentAssessment?.id,
    hasAssessment: currentAssessment !== null,
    hasProfile,
    hasCanvas,
    hasBreakthroughSelection:
      store.breakthroughSelection !== null &&
      store.breakthroughSelection.selected_elements.length >= 1,
    hasDirectionDraft: store.directionData !== null,
    hasDirectionSelection: store.directionSelection !== null,
    hasScenarios,
    scenarioCount: store.scenarioRecommendation?.top_scenarios?.length ?? 0,
    hasCompetitiveness,
    hasEndgame,
    progress,
    profileMode: store.profileMode,
  });

  const workflowModules: WorkflowModule[] = currentAssessment
    ? workflowState.actionModules.map((module) => {
        const loading =
          (module.key === "profile" && generateProfile.isPending) ||
          (module.key === "canvas" && generateCanvas.isPending) ||
          (module.key === "directions" && expandDirections.isPending) ||
          (module.key === "scenarios" && generateScenarios.isPending) ||
          (module.key === "competitiveness" &&
            generateCompetitiveness.isPending) ||
          (module.key === "endgame" && generateEndgame.isPending);
        const paymentLocked =
          hasCanvas && requiresPayment && isPaidWorkflowKey(module.key);
        const onClick =
          module.key === "profile"
            ? handleGenerateProfile
            : module.key === "canvas"
              ? handleGenerateCanvas
              : module.key === "breakthrough"
                ? handleGenerateBreakthrough
                : module.key === "directions"
                  ? handleGenerateDirections
                  : module.key === "scenarios"
                    ? handleGenerateScenarios
                    : module.key === "competitiveness"
                      ? handleGenerateCompetitiveness
                      : handleGenerateEndgame;

        return {
          ...module,
          color:
            module.key === "profile" || module.key === "scenarios"
              ? "success"
              : module.key === "breakthrough" || module.key === "competitiveness"
                ? "warn"
                : "accent",
          disabled: paymentLocked ? false : module.disabled || loading,
          loading: paymentLocked ? false : loading,
          onClick: paymentLocked ? handleOpenPaymentDialog : onClick,
          paymentLocked,
        };
      })
    : [];

  const resultCards: ResultCardItem[] = currentAssessment
    ? workflowState.resultCards.map((card) => {
        const paymentLocked =
          hasCanvas && requiresPayment && isPaidWorkflowKey(card.key);
        return {
          ...card,
          state: paymentLocked ? "locked" : card.state,
          done: paymentLocked ? false : card.done,
          statusLabel: paymentLocked ? "付费解锁" : card.statusLabel,
          paymentLocked,
          link: paymentLocked
            ? undefined
            : (() => {
          if (!card.isNavigable) return undefined;
          if (card.key === "profile") return `/assessment/${currentAssessment.id}/profile`;
          if (card.key === "canvas") return `/assessment/${currentAssessment.id}/canvas`;
          if (card.key === "breakthrough") return `/assessment/${currentAssessment.id}/scoring`;
          if (card.key === "directions") return `/assessment/${currentAssessment.id}/directions`;
          if (card.key === "scenarios") return getScenarioResultPath(currentAssessment.id);
          if (card.key === "competitiveness") {
            return getCompetitivenessResultPath(currentAssessment.id);
          }
          return `/assessment/${currentAssessment.id}/endgame`;
        })(),
        };
      })
    : [];

  const completedResultCount = resultCards.filter((card) => card.done).length;
  const activeGeneration = workflowModules.find((module) => module.loading);

  const filledCount = Object.values(form).filter(
    (v) => typeof v === "string" && v.trim().length > 0,
  ).length;

  return (
    <section className="flex flex-col gap-6">
      {/* 前置材料导入（可选） */}
      {!assessmentId && !currentAssessment ? (
        <div className="card">
          <button
            type="button"
            onClick={() => setShowImport(!showImport)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <p className="section-label">可选步骤</p>
              <h2 className="section-heading">前置材料导入（可选）</h2>
            </div>
            <span className="text-sm text-muted-foreground">
              {showImport ? "收起 ▲" : "展开 ▼"}
            </span>
          </button>
          {showImport ? (
            <div className="mt-4">
              <IntakeImportSection onImported={setLocalPrefillSessionId} />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* 企业问卷录入区 */}
      <section>
        {currentAssessment && !isQuestionnaireExpanded ? (
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="section-label">企业问卷已录入</p>
                <p className="mt-2 text-sm text-warm-text">
                  企业：{currentAssessment.company_name || "—"}　行业：{currentAssessment.industry || "—"}　规模：{currentAssessment.company_size || "—"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  已填写：{filledCount} / 11 项
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => setIsQuestionnaireExpanded(true)}>
                展开查看
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <AssessmentFormSection
              assessmentId={assessmentId}
              prefillSummary={prefillSummary}
              prefillError={prefillError}
              prefillFieldMeta={prefillQuery.data?.field_meta ?? null}
              form={form}
              onFormChange={updateField}
              assessment={currentAssessment}
              onReset={handleResetForm}
            />
            {currentAssessment ? (
              <div className="mt-4 text-right">
                <Button variant="ghost" size="sm" onClick={() => setIsQuestionnaireExpanded(false)}>
                  收起问卷
                </Button>
              </div>
            ) : null}
          </div>
        )}
      </section>

      {currentAssessment && hasCanvas && requiresPayment && entitlement ? (
        <PaymentUnlockPanel
          assessmentId={currentAssessment.id}
          entitlement={entitlement}
          onUnlocked={handlePaymentUnlocked}
        />
      ) : null}

      {/* 操作区 + 结果摘要区 */}
      {currentAssessment ? (
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          {/* 左侧：操作区 */}
          <div className="card">
            <p className="section-label">操作</p>
            <h2 className="section-heading">逐步生成</h2>
            <div className="mt-6 grid gap-3">
              {workflowModules.map(({ key, ...actionProps }) => (
                <ActionBtn key={key} {...actionProps} />
              ))}
            </div>
            {workflowModules.some((module) => module.loading) ? (
              <GenerationWaitHint label={generateProfile.isPending ? "正在生成企业画像" : "正在生成分析结果"} />
            ) : null}
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              刷新页面后会自动从后端恢复当前 Assessment 状态。重新生成上游模块时，
              下游结果会自动失效并需要重新生成。
            </p>
          </div>

          {/* 右侧：结果摘要区 */}
          <div className="space-y-2">
            <p className="section-label">结果摘要</p>
            <div className="rounded-2xl border border-warm-border-light bg-warm-surface px-5 py-4">
              <div className="flex items-center justify-between gap-3 text-sm">
                <h3 className="font-medium text-warm-text">生成进度</h3>
                <span className="text-muted-foreground">
                  已完成 {completedResultCount} / {resultCards.length} 项
                </span>
              </div>
              <Progress
                aria-label="生成进度"
                aria-valuetext={`已完成 ${completedResultCount} / ${resultCards.length} 项`}
                value={completedResultCount}
                max={resultCards.length}
                className="mt-3"
              />
              {activeGeneration ? (
                <p aria-live="polite" className="mt-2 text-xs text-muted-foreground">
                  正在{activeGeneration.hasResult ? "重新" : ""}生成{activeGeneration.label}
                </p>
              ) : null}
            </div>
            {resultCards.map((card) => (
              <ResultSummaryRow
                key={card.key}
                card={card}
                onUnlockClick={handleOpenPaymentDialog}
              />
            ))}
            <ResultSummaryRow
              card={{
                key: "dashboard",
                label: "结果仪表盘",
                state: hasDashboard ? "done" : "locked",
                done: hasDashboard,
                statusLabel: hasDashboard ? "可查看" : "待生成",
                link: hasDashboard
                  ? getResultsDashboardPath(currentAssessment.id)
                  : undefined,
              }}
            />
          </div>
        </div>
      ) : null}

      {currentAssessment && entitlement ? (
        <Dialog open={isPaymentDialogOpen} onOpenChange={setIsPaymentDialogOpen}>
          <DialogContent className="sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle>解锁完整 AI 创新方案</DialogTitle>
              <DialogDescription>
                完成支付后仅解锁当前评估，后端会继续强制校验权益。
              </DialogDescription>
            </DialogHeader>
            <PaymentUnlockPanel
              assessmentId={currentAssessment.id}
              entitlement={entitlement}
              compact
              onUnlocked={handlePaymentUnlocked}
            />
          </DialogContent>
        </Dialog>
      ) : null}

    </section>
  );
}

function ResultSummaryRow({
  card,
  onUnlockClick,
}: {
  card: ResultCardItem;
  onUnlockClick?: () => void;
}) {
  const isLocked = card.state === "locked";
  const badgeCls = card.done
    ? "badge-success"
    : card.state === "pending-review" || card.state === "available"
      ? "badge-warning"
      : "badge-muted";

  const content = (
    <div
      className={`flex items-center justify-between rounded-2xl border px-5 py-3.5 ${
        isLocked
          ? "border-warm-border-light bg-warm-inset opacity-70"
          : "border-warm-border-light bg-warm-surface hover:shadow-sm transition"
      } ${(!isLocked && card.link) || card.paymentLocked ? "cursor-pointer" : ""}`}
    >
      <span className={`font-medium text-sm ${isLocked ? "text-muted-foreground" : "text-warm-text"}`}>
        {card.label}
      </span>
      <span className={`badge text-xs ${badgeCls}`}>{card.statusLabel}</span>
    </div>
  );

  if (card.link && !isLocked) {
    return (
      <Link href={card.link} target="_blank" rel="noopener noreferrer">
        {content}
      </Link>
    );
  }
  if (card.paymentLocked) {
    return (
      <button
        type="button"
        onClick={onUnlockClick}
        className="block w-full text-left"
      >
        {content}
      </button>
    );
  }
  return content;
}
