"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, generateAssessmentReport, getAssessmentDetail } from "@/lib/api";
import { isPaymentRequired } from "@/lib/payment-entitlement";
import type { AssessmentDetailResponse, ReportDocumentResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";

export function ReportPreviewViewer({ assessmentId }: { assessmentId: string }) {
  const router = useRouter();
  const [detail, setDetail] = useState<AssessmentDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [reportMode, setReportMode] = useState<"template" | "llm">("template");

  const loadDetail = useCallback(() => {
    let active = true;
    setIsLoading(true); setError(null);
    getAssessmentDetail(assessmentId)
      .then((payload) => { if (active) setDetail(payload); })
      .catch((nextError) => { if (active) setError(nextError instanceof Error ? nextError.message : "报告状态加载失败。"); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [assessmentId]);

  useEffect(() => {
    return loadDetail();
  }, [loadDetail]);

  const handlePaymentUnlocked = useCallback(() => {
    loadDetail();
  }, [loadDetail]);

  async function handleGenerateReport() {
    setIsGenerating(true); setError(null);
    try {
      const reportResponse: ReportDocumentResponse = await generateAssessmentReport(assessmentId, reportMode);
      router.push(`/reports/${reportResponse.report_id}`);
    } catch (nextError) { setError(formatReportError(nextError, reportMode)); }
    finally { setIsGenerating(false); }
  }

  if (isLoading) return (
    <div className="card space-y-4">
      <div className="space-y-2"><Skeleton className="h-6 w-36 rounded-xl" /><Skeleton className="h-8 w-64 rounded-xl" /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64 rounded-xl" /><Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  );

  if (error) return (
    <div className="rounded-xl msg-error p-6 text-sm space-y-4">
      <div>
        <p className="font-medium">报告状态加载失败</p>
        <p className="mt-2 opacity-90">{error}</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" size="sm" onClick={loadDetail}>重试加载</Button>
        <Link href={`/assessment/${assessmentId}`} className="btn-secondary text-xs">返回 Assessment 工作台</Link>
      </div>
    </div>
  );

  if (!detail) return null;

  const assessment = detail.assessment;
  const profile = detail.company_profile;
  const canvas = detail.canvas_diagnosis;
  const scenarios = detail.scenario_recommendation;
  const existingReport = detail.generated_report;

  if (isPaymentRequired(detail.entitlement)) {
    return (
      <PaymentUnlockPanel
        assessmentId={assessmentId}
        entitlement={detail.entitlement}
        onUnlocked={handlePaymentUnlocked}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label">报告生成</p>
            <h2 className="section-heading">报告生成页</h2>
            <p className="mt-2 max-w-3xl text-sm leading-7 text-warm-secondary">
              当前页面会基于完整串行链路结果生成统一报告，包括方向确认、场景推荐、竞争力分析和核心竞争力推进策略。
            </p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-6 py-4 text-sm text-amber-800">
            <p className="font-medium">Assessment ID</p>
            <p className="mt-2 break-all font-mono text-amber-700/90">{assessment.id}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="card-inset">
          <p className="section-label">就绪检查</p>
          <h2 className="section-heading">报告生成前检查</h2>
          <div className="mt-6 space-y-3 text-sm">
            <StatusRow label="企业画像" ready={detail.progress.has_profile} text={profile ? "已生成，可直接纳入报告。" : "尚未生成，当前无法进入报告。"} />
            <StatusRow label="商业画布诊断" ready={detail.progress.has_canvas} text={canvas ? `已生成，整体评分 ${canvas.overall_score}。` : "尚未生成，当前无法进入报告。"} />
            <StatusRow label="创新方向确认" ready={detail.progress.has_directions} text={detail.progress.has_directions ? "已确认，可作为后续推导依据。" : "尚未确认，当前无法进入报告。"} />
            <StatusRow label="AI 场景推荐" ready={detail.progress.has_scenarios} text={scenarios ? `已生成 Top ${scenarios.top_scenarios.length} 推荐。` : "尚未生成，当前无法进入报告。"} />
            <StatusRow label="差异化竞争力" ready={detail.progress.has_competitiveness} text={detail.progress.has_competitiveness ? "已生成，将直接进入报告结论。" : "尚未生成，当前无法进入报告。"} />
            <StatusRow label="核心竞争力推进策略" ready={detail.progress.has_endgame} text={detail.progress.has_endgame ? "已生成，可进入最终报告。" : "尚未生成，当前无法进入报告。"} />
            <StatusRow label="已有报告" ready={detail.progress.has_report} text={existingReport ? `已存在报告：${existingReport.title}` : "尚未生成报告。"} />
          </div>
          {!detail.progress.ready_for_report ? (
            <div className="mt-6 rounded-xl msg-warning p-6 text-sm leading-7">还不能生成报告。请先按顺序完成企业画像、商业画布、方向确认、场景推荐、竞争力分析和核心竞争力推进策略。</div>
          ) : null}
        </div>

        <div className="card">
          <p className="section-label">操作</p>
          <h2 className="section-heading">生成与回看</h2>
          <div className="mt-6 grid gap-3">
            <div className="rounded-xl border border-warm-border-light bg-warm-inset px-4 py-4">
              <p className="mb-3 font-medium text-warm-text">报告生成模式</p>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="reportMode" value="template" checked={reportMode === "template"}
                    onChange={() => setReportMode("template")} className="h-4 w-4 accent-warm-accent" />
                  <span className="text-sm text-warm-text">模板生成（快速）</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="reportMode" value="llm" checked={reportMode === "llm"}
                    onChange={() => setReportMode("llm")} className="h-4 w-4 accent-warm-accent" />
                  <span className="text-sm text-warm-text">LLM 增强（智能）</span>
                </label>
              </div>
              <p className="mt-2 text-xs text-warm-muted">
                {reportMode === "template" ? "模板模式：使用结构化模板快速生成报告" : "LLM 模式：优先使用大语言模型增强表达，失败或超时会自动回退到模板模式"}
              </p>
            </div>

            <button type="button" onClick={handleGenerateReport} disabled={!detail.progress.ready_for_report || isGenerating} className="btn-primary">
              {isGenerating ? "正在生成报告..." : existingReport ? "重新生成报告" : "生成报告"}
            </button>
            {isGenerating ? <GenerationWaitHint label="正在生成报告" /> : null}

            {existingReport ? (
              <Link href={`/reports/${existingReport.report_id}`} className="btn-secondary" target="_blank" rel="noopener noreferrer">查看已有报告</Link>
            ) : null}
            <Link href={`/assessment/${assessmentId}`} className="btn-secondary">返回 Assessment 工作台</Link>
          </div>

          <div className="mt-6 rounded-xl border border-warm-border-light bg-warm-inset p-6 text-sm leading-7 text-warm-secondary">
            <p>报告生成逻辑当前为模板化生成，不依赖 API Key，也不会自由编造真实公司案例或 ROI 数字。</p>
            <p className="mt-3">选择 LLM 模式时，页面会在结果页展示是否实际使用了 LLM、是否使用了 RAG，以及所有 warning / 回退提示。</p>
            <p className="mt-3">生成完成后可在报告预览页下载 Markdown、Word 或打开打印版；如果下载失败，请先确认后端服务仍在运行。</p>
          </div>

          {error ? <div className="mt-6 rounded-xl msg-error p-4 text-sm">{error}</div> : null}
        </div>
      </div>
    </div>
  );
}

function StatusRow({ label, ready, text }: { label: string; ready: boolean; text: string }) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-surface px-4 py-4">
      <div className="flex items-center justify-between gap-4">
        <p className="font-medium text-warm-text">{label}</p>
        <span className={`badge ${ready ? "badge-success" : "badge-muted"}`}>{ready ? "已就绪" : "未完成"}</span>
      </div>
      <p className="mt-3 leading-7 text-warm-secondary">{text}</p>
    </div>
  );
}

function formatReportError(error: unknown, reportMode: "template" | "llm"): string {
  if (error instanceof ApiError) {
    if (error.status === 400) return "报告前置步骤未完成。请先在 Assessment 工作台依次完成企业画像、商业画布、方向确认、场景推荐、竞争力分析和核心竞争力推进策略，再回来生成报告。";
    if (error.status >= 500) return "报告生成时后端发生异常。请稍后重试；如果问题持续存在，请检查后端日志与报告配置。";
    return error.message;
  }
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (message.includes("timeout")) return reportMode === "llm" ? "LLM 报告生成超时。系统通常会自动回退到模板模式，请重试并在结果页查看 warning。" : "请求超时，请确认后端服务状态后重试。";
    if (message.includes("failed to fetch")) return "无法连接后端服务。请确认后端已启动，并检查 NEXT_PUBLIC_API_BASE_URL 是否正确。";
    return error.message;
  }
  return "报告生成失败。";
}
