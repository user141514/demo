"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { BreakthroughSelectionPanel } from "@/components/breakthrough-selection-panel";
import { BusinessCanvasGrid } from "@/components/business-canvas-grid";
import { CompetitivenessPanel } from "@/components/competitiveness-panel";
import { DirectionExpansionPanel } from "@/components/direction-expansion-panel";
import { EndgamePanel } from "@/components/endgame-panel";
import { FollowUpDashboard } from "@/components/follow-up-dashboard";
import { ProgressStepper } from "@/components/progress-stepper";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import { PushPanel } from "@/components/push-panel";
import { ScenarioRecommendationsPanel } from "@/components/scenario-recommendations-panel";
import {
  createAssessment,
  expandDirections,
  generateAssessmentCanvas,
  generateAssessmentProfile,
  generateCompetitiveness,
  generateScenarioRecommendations,
  generateEndgame,
  getAssessmentDetail,
  getIntakeImportSession,
  getFollowUpPlan,
  recommendBreakthrough,
  selectBreakthrough,
  selectDirections,
} from "@/lib/api";
import type {
  AssessmentBreakthroughResponse,
  AssessmentCanvasResponse,
  AssessmentCreateRequest,
  AssessmentDetailResponse,
  AssessmentDirectionResponse,
  AssessmentPrefillDraft,
  AssessmentProgress,
  AssessmentResponse,
  BreakthroughSelectionResponse,
  CanvasDiagnosisResult,
  CompanyProfileResult,
  CompetitivenessResponse,
  DirectionSelectionResponse,
  EndgameResponse,
  ScenarioRecommendationResult,
  FollowUpPlan,
} from "@/lib/types";

const companySizeOptions = [
  "10人以下", "10-50人", "50-200人", "200-500人", "500人以上",
];

const revenueOptions = [
  "500万以下", "500万-3000万", "3000万-1亿", "1亿-10亿", "10亿以上",
];

const initialForm: AssessmentCreateRequest = {
  company_name: "", industry: "", company_size: "", region: "",
  annual_revenue_range: "", core_products: "", target_customers: "",
  current_challenges: "", ai_goals: "", available_data: "", notes: "",
};

const initialProgress: AssessmentProgress = {
  has_profile: false, has_canvas: false, has_breakthrough: false,
  has_directions: false, has_competitiveness: false, has_endgame: false, has_scenarios: false,
  has_cases: false, has_report: false, ready_for_report: false,
};

export function AssessmentWorkbench({
  assessmentId,
  prefillSessionId,
}: {
  assessmentId?: string;
  prefillSessionId?: string;
}) {
  const router = useRouter();
  const [form, setForm] = useState<AssessmentCreateRequest>(initialForm);
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [companyProfile, setCompanyProfile] = useState<CompanyProfileResult | null>(null);
  const [profileMode, setProfileMode] = useState<"mock" | "live" | null>(null);
  const [canvasDiagnosis, setCanvasDiagnosis] = useState<CanvasDiagnosisResult | null>(null);
  const [scenarioRecommendation, setScenarioRecommendation] = useState<ScenarioRecommendationResult | null>(null);
  const [breakthroughData, setBreakthroughData] = useState<AssessmentBreakthroughResponse | null>(null);
  const [breakthroughSelection, setBreakthroughSelection] = useState<BreakthroughSelectionResponse | null>(null);
  const [selectedBreakthroughKeys, setSelectedBreakthroughKeys] = useState<string[]>([]);
  const [directionData, setDirectionData] = useState<AssessmentDirectionResponse | null>(null);
  const [directionSelection, setDirectionSelection] = useState<DirectionSelectionResponse | null>(null);
  const [selectedDirectionIds, setSelectedDirectionIds] = useState<string[]>([]);
  const [progress, setProgress] = useState<AssessmentProgress>(initialProgress);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [canvasError, setCanvasError] = useState<string | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [breakthroughError, setBreakthroughError] = useState<string | null>(null);
  const [directionError, setDirectionError] = useState<string | null>(null);
  const [isLoadingAssessment, setIsLoadingAssessment] = useState(Boolean(assessmentId));
  const [isLoadingPrefill, setIsLoadingPrefill] = useState(Boolean(!assessmentId && prefillSessionId));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGeneratingProfile, setIsGeneratingProfile] = useState(false);
  const [isGeneratingCanvas, setIsGeneratingCanvas] = useState(false);
  const [isGeneratingScenarios, setIsGeneratingScenarios] = useState(false);
  const [isGeneratingBreakthrough, setIsGeneratingBreakthrough] = useState(false);
  const [isSelectingBreakthrough, setIsSelectingBreakthrough] = useState(false);
  const [isGeneratingDirections, setIsGeneratingDirections] = useState(false);
  const [isSelectingDirections, setIsSelectingDirections] = useState(false);
  const [isGeneratingCompetitiveness, setIsGeneratingCompetitiveness] = useState(false);
  const [competitivenessData, setCompetitivenessData] = useState<CompetitivenessResponse | null>(null);
  const [competitivenessError, setCompetitivenessError] = useState<string | null>(null);
  const [isGeneratingEndgame, setIsGeneratingEndgame] = useState(false);
  const [endgameData, setEndgameData] = useState<EndgameResponse | null>(null);
  const [endgameError, setEndgameError] = useState<string | null>(null);
  const [followUpPlan, setFollowUpPlan] = useState<FollowUpPlan | null>(null);
  const [isLoadingFollowUp, setIsLoadingFollowUp] = useState(false);
  const [followUpError, setFollowUpError] = useState<string | null>(null);
  const [prefillError, setPrefillError] = useState<string | null>(null);
  const [prefillSummary, setPrefillSummary] = useState<{
    importSessionId: string;
    mappedCount: number;
  } | null>(null);
  const [appliedPrefillSessionId, setAppliedPrefillSessionId] = useState<string | null>(null);

  const answeredCount = useMemo(() => {
    return Object.values(form).filter((value) => typeof value === "string" && value.trim().length > 0).length;
  }, [form]);

  useEffect(() => {
    if (!assessmentId) { setIsLoadingAssessment(false); return; }
    let active = true;
    setIsLoadingAssessment(true);
    setLoadError(null);
    getAssessmentDetail(assessmentId)
      .then((detail) => { if (!active) return; applyAssessmentDetail(detail); })
      .catch((error) => { if (!active) return; setLoadError(error instanceof Error ? error.message : "Assessment 加载失败。"); })
      .finally(() => { if (active) setIsLoadingAssessment(false); });
    return () => { active = false; };
  }, [assessmentId]);

  useEffect(() => {
    if (assessmentId || !prefillSessionId) {
      setIsLoadingPrefill(false);
      return;
    }
    if (appliedPrefillSessionId === prefillSessionId) {
      setIsLoadingPrefill(false);
      return;
    }

    let active = true;
    setIsLoadingPrefill(true);
    setPrefillError(null);

    getIntakeImportSession(prefillSessionId)
      .then((detail) => {
        if (!active) return;
        setForm((current) => mergePrefillIntoForm(current, detail.assessment_prefill));
        setPrefillSummary({
          importSessionId: detail.import_session_id,
          mappedCount: countPrefillFields(detail.assessment_prefill),
        });
        setAppliedPrefillSessionId(detail.import_session_id);
      })
      .catch((error) => {
        if (!active) return;
        setPrefillError(error instanceof Error ? error.message : "导入预填加载失败，请稍后重试。");
      })
      .finally(() => {
        if (active) setIsLoadingPrefill(false);
      });

    return () => { active = false; };
  }, [appliedPrefillSessionId, assessmentId, prefillSessionId]);

  function applyAssessmentDetail(detail: AssessmentDetailResponse) {
    setAssessment(detail.assessment);
    setForm(mapAssessmentToForm(detail.assessment));
    setCompanyProfile(detail.company_profile);
    setProfileMode(detail.company_profile ? (detail.assessment.profile_generation_mode as "mock" | "live" | null) ?? "mock" : null);
    setCanvasDiagnosis(detail.canvas_diagnosis);
    if (detail.breakthrough_selection && detail.breakthrough_selection.length >= 1) {
      setSelectedBreakthroughKeys(detail.breakthrough_selection);
    } else { setSelectedBreakthroughKeys([]); }
    setScenarioRecommendation(detail.scenario_recommendation);
    setCompetitivenessData(detail.competitiveness);
    setEndgameData(detail.endgame);
    setProgress(detail.progress);
  }

  function updateField(key: keyof AssessmentCreateRequest, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function resetErrors() {
    setLoadError(null); setSubmitError(null); setProfileError(null);
    setCanvasError(null); setScenarioError(null); setBreakthroughError(null);
    setDirectionError(null); setCompetitivenessError(null); setEndgameError(null);
    setFollowUpError(null); setPrefillError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetErrors();
    setIsSubmitting(true);
    try {
      const createdAssessment = await createAssessment({ ...form, notes: (form.notes ?? "").trim() || null });
      setAssessment(createdAssessment);
      setCompanyProfile(null); setProfileMode(null); setCanvasDiagnosis(null);
      setBreakthroughData(null); setBreakthroughSelection(null); setSelectedBreakthroughKeys([]);
      setDirectionData(null); setDirectionSelection(null); setSelectedDirectionIds([]);
      setScenarioRecommendation(null); setProgress(initialProgress);
      router.push(`/assessment/${createdAssessment.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "问卷提交失败，请稍后重试。");
    } finally { setIsSubmitting(false); }
  }

  async function handleGenerateProfile() {
    if (!assessment) return;
    setProfileError(null); setCanvasError(null); setScenarioError(null); setBreakthroughError(null);
    setIsGeneratingProfile(true);
    try {
      const nextProfile = await generateAssessmentProfile(assessment.id);
      setAssessment(nextProfile.assessment); setCompanyProfile(nextProfile.profile);
      setProfileMode(nextProfile.generation_mode); setCanvasDiagnosis(null);
      setBreakthroughData(null); setBreakthroughSelection(null); setSelectedBreakthroughKeys([]);
      setDirectionData(null); setDirectionSelection(null); setSelectedDirectionIds([]);
      setScenarioRecommendation(null);
      setProgress(computeProgress({ hasAssessment: true, hasProfile: true, hasCanvas: false, hasScenarios: false }));
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "企业画像生成失败，请稍后重试。");
    } finally { setIsGeneratingProfile(false); }
  }

  async function handleGenerateCanvas() {
    if (!assessment) return;
    setCanvasError(null); setScenarioError(null); setBreakthroughError(null);
    setIsGeneratingCanvas(true);
    try {
      const nextCanvas = await generateAssessmentCanvas(assessment.id);
      applyCanvasResponse(nextCanvas);
      setBreakthroughData(null); setBreakthroughSelection(null); setSelectedBreakthroughKeys([]);
      setDirectionData(null); setDirectionSelection(null); setSelectedDirectionIds([]);
      setScenarioRecommendation(null);
      setProgress(computeProgress({ hasAssessment: true, hasProfile: true, hasCanvas: true, hasScenarios: false }));
    } catch (error) {
      setCanvasError(error instanceof Error ? error.message : "商业画布诊断失败，请稍后重试。");
    } finally { setIsGeneratingCanvas(false); }
  }

  async function handleGenerateScenarios() {
    if (!assessment) return;
    setScenarioError(null);
    setIsGeneratingScenarios(true);
    try {
      const nextRecommendations = await generateScenarioRecommendations(assessment.id);
      setAssessment(nextRecommendations.assessment);
      setScenarioRecommendation(nextRecommendations.scenario_recommendation);
      setProgress(computeProgress({ hasAssessment: true, hasProfile: companyProfile !== null, hasCanvas: canvasDiagnosis !== null, hasScenarios: true }));
    } catch (error) {
      setScenarioError(error instanceof Error ? error.message : "场景推荐失败，请稍后重试。");
    } finally { setIsGeneratingScenarios(false); }
  }

  async function handleGenerateBreakthrough() {
    if (!assessment) return;
    setBreakthroughError(null);
    setIsGeneratingBreakthrough(true);
    try {
      const result = await recommendBreakthrough(assessment.id);
      setBreakthroughData(result);
      if (result.breakthrough_selection && result.breakthrough_selection.selected_elements.length >= 1) {
        setBreakthroughSelection(result.breakthrough_selection);
        setSelectedBreakthroughKeys(result.breakthrough_selection.selected_elements.map((e) => e.key));
      } else {
        setBreakthroughSelection(null);
        setSelectedBreakthroughKeys(result.breakthrough_recommendation.recommended_keys);
      }
    } catch (error) {
      setBreakthroughError(error instanceof Error ? error.message : "突破要素推荐失败，请稍后重试。");
    } finally { setIsGeneratingBreakthrough(false); }
  }

  function handleToggleBreakthroughKey(key: string) {
    setSelectedBreakthroughKeys((current) => {
      if (current.includes(key)) return current.filter((k) => k !== key);
      if (current.length >= 3) return current;
      return [...current, key];
    });
  }

  async function handleSelectBreakthrough() {
    if (!assessment || selectedBreakthroughKeys.length < 1) return;
    setBreakthroughError(null);
    setIsSelectingBreakthrough(true);
    try {
      const result = await selectBreakthrough(assessment.id, {
        selected_keys: selectedBreakthroughKeys, selection_mode: "system_recommended",
      });
      setBreakthroughSelection(result);
      setBreakthroughData((prev) => prev ? { ...prev, breakthrough_selection: result } : null);
      setProgress(computeProgress({
        hasAssessment: true, hasProfile: companyProfile !== null,
        hasCanvas: canvasDiagnosis !== null, hasBreakthrough: true,
        hasScenarios: scenarioRecommendation !== null,
      }));
    } catch (error) {
      setBreakthroughError(error instanceof Error ? error.message : "突破要素保存失败，请稍后重试。");
    } finally { setIsSelectingBreakthrough(false); }
  }

  async function handleGenerateDirections() {
    if (!assessment) return;
    setDirectionError(null);
    setIsGeneratingDirections(true);
    try {
      const result = await expandDirections(assessment.id);
      setDirectionData(result);
      if (result.direction_selection && result.direction_selection.selected_directions.length > 0) {
        setDirectionSelection(result.direction_selection);
        setSelectedDirectionIds(result.direction_selection.selected_directions.map((d) => d.direction_id));
      } else { setDirectionSelection(null); setSelectedDirectionIds([]); }
    } catch (error) {
      setDirectionError(error instanceof Error ? error.message : "方向延展生成失败，请稍后重试。");
    } finally { setIsGeneratingDirections(false); }
  }

  function handleToggleDirectionId(id: string) {
    setSelectedDirectionIds((current) => {
      if (current.includes(id)) return current.filter((d) => d !== id);
      if (current.length >= 6) return current;
      return [...current, id];
    });
  }

  async function handleSelectDirections() {
    if (!assessment || selectedDirectionIds.length < 1) return;
    setDirectionError(null);
    setIsSelectingDirections(true);
    try {
      const result = await selectDirections(assessment.id, { selected_direction_ids: selectedDirectionIds });
      setDirectionSelection(result);
      setDirectionData((prev) => prev ? { ...prev, direction_selection: result } : null);
      setProgress(computeProgress({
        hasAssessment: true,
        hasProfile: companyProfile !== null,
        hasCanvas: canvasDiagnosis !== null,
        hasBreakthrough: breakthroughSelection !== null && breakthroughSelection.selected_elements.length >= 1,
        hasDirections: true,
        hasScenarios: scenarioRecommendation !== null,
      }));
    } catch (error) {
      setDirectionError(error instanceof Error ? error.message : "方向选择保存失败，请稍后重试。");
    } finally { setIsSelectingDirections(false); }
  }

  async function handleGenerateCompetitiveness() {
    if (!assessment) return;
    setCompetitivenessError(null);
    setIsGeneratingCompetitiveness(true);
    try {
      const result = await generateCompetitiveness(assessment.id);
      setCompetitivenessData(result);
      setScenarioRecommendation(null);
      setProgress(computeProgress({
        hasAssessment: true, hasProfile: companyProfile !== null,
        hasCanvas: canvasDiagnosis !== null,
        hasBreakthrough: breakthroughSelection !== null && breakthroughSelection.selected_elements.length >= 1,
        hasScenarios: false,
      }));
    } catch (error) {
      setCompetitivenessError(error instanceof Error ? error.message : "竞争力分析生成失败，请稍后重试。");
    } finally { setIsGeneratingCompetitiveness(false); }
  }

  async function handleGenerateEndgame() {
    if (!assessment) return;
    setEndgameError(null);
    setIsGeneratingEndgame(true);
    try {
      const result = await generateEndgame(assessment.id);
      setEndgameData(result);
    } catch (error) {
      setEndgameError(error instanceof Error ? error.message : "核心竞争力推进策略生成失败，请稍后重试。");
    } finally { setIsGeneratingEndgame(false); }
  }

  async function handleLoadFollowUp() {
    if (!assessment) return;
    setFollowUpError(null);
    setIsLoadingFollowUp(true);
    try { const plan = await getFollowUpPlan(assessment.id); setFollowUpPlan(plan); }
    catch (error) { setFollowUpError(error instanceof Error ? error.message : "加载跟进计划失败"); }
    finally { setIsLoadingFollowUp(false); }
  }

  function applyCanvasResponse(response: AssessmentCanvasResponse) {
    setAssessment(response.assessment);
    setCanvasDiagnosis(response.canvas_diagnosis);
  }

  function handleResetForm() {
    if (assessmentId) { router.push("/assessment"); return; }
    setForm(initialForm); setAssessment(null); setCompanyProfile(null);
    setProfileMode(null); setCanvasDiagnosis(null); setBreakthroughData(null);
    setBreakthroughSelection(null); setSelectedBreakthroughKeys([]);
    setDirectionData(null); setDirectionSelection(null); setSelectedDirectionIds([]);
    setScenarioRecommendation(null); setProgress(initialProgress);
    resetErrors();
  }

  if (isLoadingAssessment || isLoadingPrefill) {
    return <div className="card text-sm text-warm-secondary">正在加载问卷状态...</div>;
  }

  if (loadError) {
    return <div className="rounded-xl msg-error p-6 text-sm">{loadError}</div>;
  }

  return (
    <section className="flex flex-col gap-6">
      <ProgressStepper hasAssessment={assessment !== null} progress={progress} />

      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        {/* Assessment form */}
        <form onSubmit={handleSubmit} className="card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="section-label">问卷录入</p>
              <h2 className="section-heading">企业问卷录入</h2>
              {assessment ? <p className="mt-2 text-sm text-warm-muted">当前 Assessment ID：{assessment.id}</p> : null}
            </div>
            <span className="badge badge-accent">已填写 {answeredCount} / 11 项</span>
          </div>

          {prefillSummary ? (
            <div className="mt-4 rounded-xl msg-info p-4 text-sm">
              已从前置材料带入 {prefillSummary.mappedCount} / 11 个字段。
              缺失项可以继续在当前问卷补充，不会阻塞提交。
            </div>
          ) : null}

          {prefillError ? <div className="mt-4 rounded-xl msg-error p-4 text-sm">{prefillError}</div> : null}

          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <Field label="企业名称" required>
              <input value={form.company_name} onChange={(e) => updateField("company_name", e.target.value)} className="input-field" placeholder="例如：某某制造科技有限公司" />
            </Field>
            <Field label="所属行业" required>
              <input value={form.industry} onChange={(e) => updateField("industry", e.target.value)} className="input-field" placeholder="例如：装备制造 / 医疗器械 / 连锁零售" />
            </Field>
            <Field label="企业规模" required>
              <select value={form.company_size} onChange={(e) => updateField("company_size", e.target.value)} className="input-field">
                <option value="">请选择企业规模</option>
                {companySizeOptions.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="所在区域" required>
              <input value={form.region} onChange={(e) => updateField("region", e.target.value)} className="input-field" placeholder="例如：上海 / 苏州 / 深圳" />
            </Field>
            <Field label="年营收范围" required>
              <select value={form.annual_revenue_range} onChange={(e) => updateField("annual_revenue_range", e.target.value)} className="input-field">
                <option value="">请选择年营收范围</option>
                {revenueOptions.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </Field>
            <Field label="可用数据/系统基础" required>
              <textarea value={form.available_data} onChange={(e) => updateField("available_data", e.target.value)} className="input-field" placeholder="例如：ERP、CRM、生产报工、客服记录、Excel 台账等" />
            </Field>
          </div>

          <div className="mt-5 grid gap-5">
            <Field label="核心产品/服务" required>
              <textarea value={form.core_products} onChange={(e) => updateField("core_products", e.target.value)} className="input-field" placeholder="请描述当前主要产品、服务或解决方案" />
            </Field>
            <Field label="目标客户" required>
              <textarea value={form.target_customers} onChange={(e) => updateField("target_customers", e.target.value)} className="input-field" placeholder="例如：大型制造企业、连锁门店总部、区域经销商等" />
            </Field>
            <Field label="当前经营/管理挑战" required>
              <textarea value={form.current_challenges} onChange={(e) => updateField("current_challenges", e.target.value)} className="input-field" placeholder="例如：销售线索跟进低效、订单交付波动、客服响应慢、数据分散" />
            </Field>
            <Field label="希望通过 AI 达成的目标" required>
              <textarea value={form.ai_goals} onChange={(e) => updateField("ai_goals", e.target.value)} className="input-field" placeholder="例如：提升销售转化、优化排产、减少客服重复劳动、沉淀知识库" />
            </Field>
            <Field label="补充说明">
              <textarea value={form.notes ?? ""} onChange={(e) => updateField("notes", e.target.value)} className="input-field" placeholder="选填：补充战略方向、组织现状、预算约束、负责人等" />
            </Field>
          </div>

          {submitError ? <div className="mt-5 rounded-xl msg-error p-4 text-sm">{submitError}</div> : null}

          <div className="mt-6 flex flex-wrap gap-3">
            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "提交中..." : assessmentId ? "另存为新问卷" : "提交企业问卷"}
            </button>
            <button type="button" onClick={handleResetForm} className="btn-secondary">
              {assessmentId ? "新建空白问卷" : "清空问卷"}
            </button>
          </div>
        </form>

        {/* Status + Actions sidebar */}
        <div className="flex flex-col gap-6">
          <div className="card-inset">
            <p className="section-label">工作流</p>
            <h2 className="section-heading">当前状态</h2>
            <div className="mt-5 space-y-3">
              <StepItem title="企业问卷" status={assessment ? "done" : "current"} description={assessment ? `问卷已创建：${assessment.id}` : "先录入企业信息并创建问卷。"} />
              <StepItem title="企业画像" status={progress.has_profile ? "done" : assessment ? "current" : "pending"} description={companyProfile ? `画像已存在，模式：${profileMode ?? "mock"}` : "尚未生成企业画像。"} />
              <StepItem title="商业画布诊断" status={progress.has_canvas ? "done" : progress.has_profile ? "current" : "pending"} description={canvasDiagnosis ? `已生成 9 格诊断，总体分：${canvasDiagnosis.overall_score}` : "尚未生成商业画布。"} />
              <StepItem title="突破要素选择" status={progress.has_breakthrough ? "done" : progress.has_canvas ? "current" : "pending"} description={breakthroughSelection ? `已选择 ${breakthroughSelection.selected_elements.length} 个要素` : "尚未选择突破要素。"} />
              <StepItem title="场景推荐" status={progress.has_scenarios ? "done" : progress.has_directions ? "current" : "pending"} description={scenarioRecommendation ? `已生成 Top 3，评分方法：${scenarioRecommendation.scoring_method}` : "尚未生成 AI 场景推荐。"} />
              <StepItem title="报告草稿" status={progress.ready_for_report ? "current" : "pending"} description={progress.ready_for_report ? "上下文已齐备，可以进入报告草稿页。" : "需补齐画像、画布、方向、场景、竞争力和终局后才可进入。"} />
            </div>
          </div>

          <div className="card">
            <p className="section-label">操作</p>
            <h2 className="section-heading">生成与回看</h2>
            <div className="mt-5 grid gap-3">
              <ActionBtn onClick={handleGenerateProfile} disabled={!assessment || isGeneratingProfile} color="success" loading={isGeneratingProfile} hasResult={!!companyProfile} label="企业画像" />
              <ActionBtn onClick={handleGenerateCanvas} disabled={!assessment || !progress.has_profile || isGeneratingCanvas} color="accent" loading={isGeneratingCanvas} hasResult={!!canvasDiagnosis} label="商业画布" />
              <ActionBtn onClick={handleGenerateBreakthrough} disabled={!assessment || !progress.has_canvas || isGeneratingBreakthrough} color="warn" loading={isGeneratingBreakthrough} hasResult={!!breakthroughData} label="突破要素推荐" />
              <ActionBtn onClick={handleGenerateDirections} disabled={!assessment || !progress.has_canvas || isGeneratingDirections} color="accent" loading={isGeneratingDirections} hasResult={!!directionData} label="创新方向延展" />
              <ActionBtn onClick={handleGenerateScenarios} disabled={!assessment || !progress.has_canvas || isGeneratingScenarios} color="success" loading={isGeneratingScenarios} hasResult={!!scenarioRecommendation} label="Top 3 场景推荐" />
            </div>
            <div className="mt-3 grid gap-3">
              <ActionBtn onClick={handleGenerateCompetitiveness} disabled={!assessment || !progress.has_canvas || isGeneratingCompetitiveness} color="warn" loading={isGeneratingCompetitiveness} hasResult={!!competitivenessData} label="差异化竞争力分析" />
              <ActionBtn onClick={handleGenerateEndgame} disabled={!assessment || !progress.has_canvas || isGeneratingEndgame} color="accent" loading={isGeneratingEndgame} hasResult={!!endgameData} label="核心竞争力推进策略" />
              {/* 课后30天跟进暂时隐藏 <ActionBtn onClick={handleLoadFollowUp} disabled={!assessment || isLoadingFollowUp} color="success" loading={isLoadingFollowUp} hasResult={!!followUpPlan} label="课后 30 天跟进" /> */}
            </div>
            {isGeneratingProfile || isGeneratingCanvas || isGeneratingBreakthrough || isGeneratingDirections || isGeneratingScenarios || isGeneratingCompetitiveness || isGeneratingEndgame ? (
              <GenerationWaitHint />
            ) : null}
            <p className="mt-4 text-sm leading-7 text-warm-muted">
              刷新页面后会自动从后端恢复当前 Assessment 状态。重新生成上游模块时，下游结果会自动失效并需要重新生成。
            </p>
            {profileError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{profileError}</div> : null}
            {canvasError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{canvasError}</div> : null}
            {scenarioError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{scenarioError}</div> : null}
            {breakthroughError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{breakthroughError}</div> : null}
            {directionError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{directionError}</div> : null}
            {competitivenessError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{competitivenessError}</div> : null}
            {endgameError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{endgameError}</div> : null}
            {followUpError ? <div className="mt-4 rounded-xl msg-error p-3 text-sm">{followUpError}</div> : null}
          </div>
        </div>
      </div>

      {/* Company profile results */}
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label">画像结果</p>
            <h2 className="section-heading">企业画像结果</h2>
          </div>
          {companyProfile ? (
            <span className="badge badge-success">{profileMode === "mock" ? "Mock" : "Live"}</span>
          ) : null}
        </div>
        {companyProfile ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <ProfileBlock title="企业概览" content={companyProfile.company_summary} />
            <ProfileBlock title="价值主张" content={companyProfile.value_proposition} />
            <ProfileBlock title="客户与市场" content={companyProfile.customer_and_market} />
            <ProfileBlock title="运营与资源基础" content={companyProfile.operations_and_resources} />
            <ProfileBlock title="数字化与 AI 准备度" content={companyProfile.digital_and_ai_readiness} />
            <ListBlock title="关键挑战" items={companyProfile.key_challenges} />
            <ListBlock title="优先 AI 切入方向" items={companyProfile.priority_ai_directions} />
            <ListBlock title="待补充信息" items={companyProfile.missing_information} />
          </div>
        ) : (
          <div className="mt-5 empty-state">尚未生成企业画像。点击右侧按钮开始生成，或刷新后自动恢复历史结果。</div>
        )}
      </div>

      {canvasDiagnosis ? <BusinessCanvasGrid canvasDiagnosis={canvasDiagnosis} /> : <EmptyCard title="商业画布 9 格诊断" text="尚未生成商业画布。企业画像完成后可开始生成；若历史结果已存在，刷新页面会自动回看。" />}

      {breakthroughData ? (
        <BreakthroughSelectionPanel data={breakthroughData} selectedKeys={selectedBreakthroughKeys} isSelecting={isSelectingBreakthrough} onToggleElement={handleToggleBreakthroughKey} onConfirmSelection={handleSelectBreakthrough} />
      ) : null}

      {directionData ? (
        <DirectionExpansionPanel data={directionData} selectedIds={selectedDirectionIds} isSelecting={isSelectingDirections} onToggleDirection={handleToggleDirectionId} onConfirmSelection={handleSelectDirections} onNextStep={directionData.direction_selection && directionData.direction_selection.selected_directions.length > 0 && !competitivenessData ? handleGenerateCompetitiveness : undefined} />
      ) : null}

      {competitivenessData ? (
        <CompetitivenessPanel
          data={competitivenessData}
          companyName={assessment?.company_name}
          topScenarioNames={(scenarioRecommendation?.top_scenarios ?? [])
            .slice(0, 3)
            .map((item) => item.name)}
        />
      ) : null}
      {endgameData ? <EndgamePanel data={endgameData} /> : null}

      {/* 课后30天跟进暂时隐藏
      {followUpPlan && assessment ? (
        <div className="space-y-4">
          <FollowUpDashboard plan={followUpPlan} assessmentId={assessment.id} onRefresh={handleLoadFollowUp} />
          <PushPanel assessmentId={assessment.id} onPlanRefresh={handleLoadFollowUp} />
        </div>
      ) : null}
      */}

      {scenarioRecommendation && assessment ? (
        <ScenarioRecommendationsPanel
          assessmentId={assessment.id}
          readyForReport={!progress.has_competitiveness}
          scenarioRecommendation={scenarioRecommendation}
        />
      ) : (
        <EmptyCard title="Top 3 AI 场景推荐" text="尚未生成场景推荐。商业画布完成后可开始生成；若历史结果已存在，刷新页面会自动回看。" />
      )}
    </section>
  );
}

/* ── Sub-components ── */

function mapAssessmentToForm(assessment: AssessmentResponse): AssessmentCreateRequest {
  return {
    company_name: assessment.company_name, industry: assessment.industry,
    company_size: assessment.company_size, region: assessment.region,
    annual_revenue_range: assessment.annual_revenue_range,
    core_products: assessment.core_products, target_customers: assessment.target_customers,
    current_challenges: assessment.current_challenges, ai_goals: assessment.ai_goals,
    available_data: assessment.available_data, notes: assessment.notes ?? "",
  };
}

function mergePrefillIntoForm(
  currentForm: AssessmentCreateRequest,
  prefill: AssessmentPrefillDraft,
): AssessmentCreateRequest {
  const mergedEntries = Object.entries(prefill).map(([key, value]) => {
    const formKey = key as keyof AssessmentCreateRequest;
    const currentValue = typeof currentForm[formKey] === "string" ? currentForm[formKey] : currentForm[formKey] ?? "";
    const normalizedCurrent = currentValue.trim();
    const normalizedPrefill = (value ?? "").trim();

    if (normalizedCurrent || !normalizedPrefill) {
      return [formKey, currentForm[formKey]];
    }

    return [formKey, normalizedPrefill];
  });

  return {
    ...currentForm,
    ...Object.fromEntries(mergedEntries),
  };
}

function countPrefillFields(prefill: AssessmentPrefillDraft): number {
  return Object.values(prefill).filter((value) => typeof value === "string" && value.trim().length > 0).length;
}

function computeProgress(opts: {
  hasAssessment: boolean; hasProfile: boolean; hasCanvas: boolean;
  hasBreakthrough?: boolean; hasDirections?: boolean; hasCompetitiveness?: boolean;
  hasEndgame?: boolean;
  hasScenarios: boolean; hasCases?: boolean; hasReport?: boolean;
}): AssessmentProgress {
  return {
    has_profile: opts.hasAssessment && opts.hasProfile,
    has_canvas: opts.hasAssessment && opts.hasCanvas,
    has_breakthrough: opts.hasAssessment && (opts.hasBreakthrough ?? false),
    has_directions: opts.hasAssessment && (opts.hasDirections ?? false),
    has_competitiveness: opts.hasAssessment && (opts.hasCompetitiveness ?? false),
    has_endgame: opts.hasAssessment && (opts.hasEndgame ?? false),
    has_scenarios: opts.hasAssessment && opts.hasScenarios,
    has_cases: opts.hasAssessment && (opts.hasCases ?? false),
    has_report: opts.hasAssessment && (opts.hasReport ?? false),
    ready_for_report:
      opts.hasAssessment &&
      opts.hasProfile &&
      opts.hasCanvas &&
      (opts.hasBreakthrough ?? false) &&
      (opts.hasDirections ?? false) &&
      opts.hasScenarios &&
      (opts.hasCompetitiveness ?? false) &&
      (opts.hasEndgame ?? false),
  };
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2 text-sm text-warm-text">
      <span className="font-medium">
        {label}{required ? <span className="ml-1 text-warm-accent">*</span> : null}
      </span>
      {children}
    </label>
  );
}

function StepItem({ title, description, status }: { title: string; description: string; status: "pending" | "current" | "done" }) {
  const cls = status === "done" ? "step-done" : status === "current" ? "step-current" : "step-pending";
  return (
    <div className={`rounded-xl border px-4 py-3 ${cls}`}>
      <p className="font-medium text-sm">{title}</p>
      <p className="mt-1.5 text-sm leading-6 opacity-85">{description}</p>
    </div>
  );
}

function ProfileBlock({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-inset p-5">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-warm-muted">{title}</p>
      <p className="mt-3 text-sm leading-7 text-warm-text">{content}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-inset p-5">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-warm-muted">{title}</p>
      <ul className="mt-3 space-y-2">
        {items.map((item, i) => (
          <li key={`${title}-${i}`} className="rounded-lg bg-warm-surface px-4 py-3 text-sm text-warm-text">{item}</li>
        ))}
      </ul>
    </div>
  );
}

function EmptyCard({ title, text }: { title: string; text: string }) {
  return (
    <div className="card-inset">
      <p className="section-label">{title}</p>
      <p className="mt-4 text-sm leading-7 text-warm-muted">{text}</p>
    </div>
  );
}

function ActionBtn({
  onClick, disabled, color, loading, hasResult, label,
}: {
  onClick: () => void; disabled: boolean; color: "accent" | "success" | "warn";
  loading: boolean; hasResult: boolean; label: string;
}) {
  const colorCls =
    color === "success" ? "btn-success" :
    color === "warn" ? "inline-flex items-center justify-center rounded-full bg-warm-warning px-6 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50 shadow-sm" :
    "btn-primary";
  const verb = loading ? "生成中..." : hasResult ? `重新生成${label}` : `开始生成${label}`;
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={colorCls}>
      {loading ? `${label}生成中...` : hasResult ? `重新生成${label}` : `生成${label}`}
    </button>
  );
}
