"use client";

import React from "react";
import Link from "next/link";

import { useAssessmentDetail } from "@/hooks";
import { BusinessCanvasGrid } from "@/components/business-canvas-grid";
import { CompetitivenessPanel } from "@/components/competitiveness-panel";
import { EndgamePanel } from "@/components/endgame-panel";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { SyncFeedbackPanel } from "@/components/sync-feedback-panel";
import { ReportExportActions } from "@/app/assessment/[assessmentId]/results/report-export-actions";
import { isPaymentRequired } from "@/lib/payment-entitlement";
import type { ScenarioRecommendationItem } from "@/lib/types";

const BREAKTHROUGH_LABELS: Record<string, string> = {
  key_partnerships: "关键合作伙伴",
  key_activities: "关键业务活动",
  key_resources: "关键资源",
  value_propositions: "价值主张",
  customer_relationships: "客户关系",
  channels: "渠道通路",
  customer_segments: "客户细分",
  cost_structure: "成本结构",
  revenue_streams: "收入来源",
};

function resolveBreakthroughLabel(value: string) {
  return BREAKTHROUGH_LABELS[value] ?? value;
}

function normalizeScenarioText(value: string) {
  return value.replace(/\s+/g, "").replace(/[：:；;，,。.!！?？]/g, "");
}

function stripScenarioEffectLeadIn(expectedEffects: string) {
  return expectedEffects.replace(/^支撑方向：.*?[；;]/, "").trim();
}

function trimScenarioSummaryLeadIn(summary: string) {
  const trimmed = summary.trim();
  if (!trimmed.includes("围绕") || !trimmed.includes("结合")) {
    return trimmed;
  }

  const shortened = trimmed.replace(
    /^围绕[\s\S]+?结合[\s\S]+?(?:[，,；;。]\s*)?(?=在)/,
    "",
  );
  return shortened.length > 0 ? shortened : trimmed;
}

function dedupeScenarioEffects(summary: string, expectedEffects: string) {
  const normalizedSummary = normalizeScenarioText(summary);
  const cleanedEffects = stripScenarioEffectLeadIn(expectedEffects);
  const segments = cleanedEffects
    .split(/[；;。]/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  const uniqueSegments = segments.filter((segment) => {
    const normalizedSegment = normalizeScenarioText(segment);
    return normalizedSegment && !normalizedSummary.includes(normalizedSegment);
  });

  if (uniqueSegments.length === 0) {
    return cleanedEffects || expectedEffects;
  }

  return uniqueSegments.join("；") + "。";
}

function dedupeScenarioEffectsAcrossCards(
  expectedEffects: string,
  previousEffects: string[],
) {
  const cleanedEffects = stripScenarioEffectLeadIn(expectedEffects);
  if (previousEffects.length === 0) {
    return cleanedEffects || expectedEffects;
  }

  const normalizedPrevious = previousEffects.map((effect) =>
    normalizeScenarioText(stripScenarioEffectLeadIn(effect)),
  );
  const segments = cleanedEffects
    .split(/[；;。]/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  const uniqueSegments = segments.filter((segment) => {
    const normalizedSegment = normalizeScenarioText(segment);
    return (
      normalizedSegment &&
      !normalizedPrevious.some((previous) => previous.includes(normalizedSegment))
    );
  });

  if (uniqueSegments.length === 0) {
    return cleanedEffects || expectedEffects;
  }

  return uniqueSegments.join("；") + "。";
}

function dedupeScenarioSummary(summary: string, previousSummaries: string[]) {
  if (previousSummaries.length === 0) {
    return summary;
  }

  const normalizedPrevious = previousSummaries.map(normalizeScenarioText);
  const segments = summary
    .split(/[；;。]/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  const uniqueSegments = segments.filter((segment) => {
    const normalizedSegment = normalizeScenarioText(segment);
    return (
      normalizedSegment &&
      !normalizedPrevious.some((previous) => previous.includes(normalizedSegment))
    );
  });

  if (uniqueSegments.length === 0) {
    return summary;
  }

  return uniqueSegments.join("；") + "。";
}

export function ResultsDashboardPageContent({
  assessmentId,
}: {
  assessmentId: string;
}) {
  const detailQuery = useAssessmentDetail(assessmentId);

  if (detailQuery.isLoading) {
    return (
      <main className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-7xl space-y-6">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      </main>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <main className="min-h-screen px-6 py-10">
        <div className="mx-auto max-w-7xl">
          <div className="space-y-4 rounded-xl p-6 text-sm msg-error">
            <p className="font-medium">加载失败</p>
            <p>
              {detailQuery.error instanceof Error
                ? detailQuery.error.message
                : "无法加载评估数据。"}
            </p>
            <button
              type="button"
              onClick={() => detailQuery.refetch()}
              className="btn-secondary text-xs"
            >
              重试
            </button>
          </div>
        </div>
      </main>
    );
  }

  const detail = detailQuery.data;
  const companyName = detail.assessment.company_name || "企业";
  const industry = detail.assessment.industry || "";
  const breakthroughs = (detail.breakthrough_selection ?? []).map(
    resolveBreakthroughLabel,
  );
  const selectedDirections =
    detail.direction_selection?.selected_directions ?? [];
  const topScenarios = detail.scenario_recommendation?.top_scenarios ?? [];
  const trimmedScenarioSummaries = topScenarios.map((scenario) =>
    trimScenarioSummaryLeadIn(scenario.summary),
  );
  const dedupedScenarioSummaries = topScenarios.map((scenario, index) =>
    dedupeScenarioSummary(
      trimmedScenarioSummaries[index] ?? scenario.summary,
      trimmedScenarioSummaries.slice(0, index),
    ),
  );
  const dedupedScenarioEffects = topScenarios.map((scenario, index) =>
    dedupeScenarioEffectsAcrossCards(
      scenario.expected_effects,
      topScenarios.slice(0, index).map((item) => item.expected_effects),
    ),
  );
  const competitivenessData = detail.competitiveness ?? null;
  const endgameData = detail.endgame ?? null;
  const paymentRequired = isPaymentRequired(detail.entitlement);

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
        <section className="page-header">
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/assessment/${assessmentId}`}
                className="btn-secondary text-xs"
              >
                返回主流程工作台
              </Link>
            </div>
            <span className="badge badge-accent">结果仪表盘</span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text">
              {companyName} AI 商业创新评估
            </h1>
            {industry ? (
              <p className="text-base leading-7 text-warm-secondary">
                {industry}
              </p>
            ) : null}

            {paymentRequired ? (
              <PaymentUnlockPanel
                assessmentId={assessmentId}
                entitlement={detail.entitlement}
                onUnlocked={() => detailQuery.refetch()}
              />
            ) : (
              <div className="rounded-2xl border border-warm-border-light bg-warm-surface p-4">
                <p className="text-sm font-medium text-warm-text">导出报告</p>
                <p className="mt-1 text-xs leading-6 text-muted-foreground">
                  可直接生成并导出 PDF / Word / Markdown。
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <ReportExportActions
                    assessmentId={assessmentId}
                    initialReportId={detail.generated_report?.report_id ?? null}
                  />
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <p className="section-label">点</p>
            <h2 className="section-heading">商业画布诊断</h2>
          </div>
          {detail.canvas_diagnosis ? (
            <BusinessCanvasGrid canvasDiagnosis={detail.canvas_diagnosis} />
          ) : (
            <EmptyStateCard
              title="商业画布诊断"
              description="无结果。请先完成企业画像和商业画布诊断。"
            />
          )}
        </section>

        <section className="space-y-4">
          <div>
            <p className="section-label">线</p>
            <h2 className="section-heading">
              选定突破要素、创新方向与 AI 推荐场景
            </h2>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <SummaryCard
              title="选定突破要素"
              items={breakthroughs}
              emptyLabel="无结果"
            />
            <SummaryCard
              title="创新方向"
              items={selectedDirections.map(
                (item) => `${item.title}｜${item.description}`,
              )}
              emptyLabel="无结果"
            />
          </div>

          {topScenarios.length > 0 ? (
            <div className="card">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="section-label">AI 推荐场景</p>
                  <h2 className="section-heading">Top 3 AI 推荐场景</h2>
                </div>
                <span className="badge badge-warning">
                  共 {topScenarios.length} 个场景
                </span>
              </div>
              <div className="mt-6 grid gap-4 xl:grid-cols-3">
                {topScenarios.map((scenario, index) => (
                  <ScenarioSummaryCard
                    key={scenario.scenario_id}
                    scenario={scenario}
                    index={index}
                    summary={dedupedScenarioSummaries[index] ?? scenario.summary}
                    expectedEffects={
                      dedupedScenarioEffects[index] ?? scenario.expected_effects
                    }
                  />
                ))}
              </div>
            </div>
          ) : (
            <EmptyStateCard
              title="AI 推荐场景"
              description="无结果。请先完成创新方向确认并生成候选场景池。"
            />
          )}
        </section>

        <section className="space-y-4">
          <div>
            <p className="section-label">线</p>
            <h2 className="section-heading">差异化竞争力报告</h2>
          </div>
          {competitivenessData ? (
            <CompetitivenessPanel
              data={competitivenessData}
              companyName={companyName}
              topScenarioNames={topScenarios.slice(0, 3).map((item) => item.name)}
            />
          ) : (
            <EmptyStateCard
              title="差异化竞争力报告"
              description="无结果。请先完成 Top 3 场景确认并生成竞争力报告。"
            />
          )}
        </section>

        <section className="space-y-4">
          <div>
            <p className="section-label">面</p>
            <h2 className="section-heading">核心竞争力推进策略</h2>
          </div>
          {endgameData ? (
            <EndgamePanel data={endgameData} />
          ) : (
            <EmptyStateCard
              title="核心竞争力推进策略"
              description="无结果。请先完成差异化竞争力分析并生成推进策略。"
            />
          )}
        </section>
      </div>

      <SyncFeedbackPanel assessmentId={assessmentId} />
    </main>
  );
}

function SummaryCard({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
}) {
  const visibleItems = items.filter((item) => item.trim().length > 0);

  return (
    <article className="rounded-2xl border border-warm-border-light bg-warm-surface p-6">
      <p className="text-sm font-semibold text-warm-accent">{title}</p>
      {visibleItems.length > 0 ? (
        <ul className="mt-4 space-y-3 text-sm leading-7 text-warm-text">
          {visibleItems.map((item, index) => (
            <li
              key={`${title}-${index}`}
              className="rounded-xl bg-warm-inset px-4 py-3"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </article>
  );
}

function ScenarioSummaryCard({
  scenario,
  index,
  summary,
  expectedEffects,
}: {
  scenario: ScenarioRecommendationItem;
  index: number;
  summary: string;
  expectedEffects: string;
}) {
  const dedupedEffects = dedupeScenarioEffects(summary, expectedEffects);

  return (
    <article className="rounded-2xl border border-warm-border-light bg-warm-surface p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">
            场景 {index + 1}
          </p>
          <h3 className="mt-2 font-heading text-xl font-bold text-warm-text">
            {scenario.name}
          </h3>
          <p className="mt-2 text-sm text-warm-accent">{scenario.category}</p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <ScenarioField label="场景描述" content={summary} />
        <ScenarioField label="预期效果" content={dedupedEffects} />
        {scenario.canvas_elements ? (
          <ScenarioField label="切入模块" content={scenario.canvas_elements} />
        ) : null}
      </div>
    </article>
  );
}

function ScenarioField({
  label,
  content,
}: {
  label: string;
  content: string;
}) {
  return (
    <div className="rounded-xl bg-warm-inset px-4 py-3">
      <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">
        {label}
      </p>
      <p className="mt-1 text-sm leading-7 text-warm-secondary">{content}</p>
    </div>
  );
}

function EmptyStateCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-warm-border-light bg-warm-surface p-6">
      <p className="text-sm font-semibold text-warm-accent">{title}</p>
      <p className="mt-3 text-sm leading-7 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
