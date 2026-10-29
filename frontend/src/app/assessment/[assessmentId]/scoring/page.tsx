"use client";

import { use, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAssessmentDetail, useExpandDirections } from "@/hooks";
import { useGetBMCScoring } from "@/hooks/use-bmc-scoring";
import { toast } from "@/hooks/use-toast";
import { formatMutationError } from "@/lib/api";
import { isPaymentRequired } from "@/lib/payment-entitlement";
import { BmcScoringMatrix } from "@/components/bmc-scoring-matrix";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { Button } from "@/components/ui/button";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import { Skeleton } from "@/components/ui/skeleton";
import { SyncFeedbackPanel } from "@/components/sync-feedback-panel";

export default function ScoringPage({
  params,
}: {
  params: Promise<{ assessmentId: string }>;
}) {
  const { assessmentId } = use(params);
  const router = useRouter();
  const detailQuery = useAssessmentDetail(assessmentId);
  const paymentRequired = isPaymentRequired(detailQuery.data?.entitlement);
  const savedScoringQuery = useGetBMCScoring(
    assessmentId,
    Boolean(detailQuery.data) && !paymentRequired,
  );
  const expandDirections = useExpandDirections();

  const hasBreakthrough =
    !!detailQuery.data?.breakthrough_selection &&
    detailQuery.data.breakthrough_selection.length >= 1;

  const handleGenerateDirections = useCallback(async () => {
    try {
      await expandDirections.mutateAsync(assessmentId);
      toast({ title: "创新方向候选已生成" });
      router.push(`/assessment/${assessmentId}/directions`);
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "创新方向候选生成"),
        variant: "destructive",
      });
    }
  }, [assessmentId, expandDirections, router]);

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
            <Button
              variant="outline"
              size="sm"
              onClick={() => detailQuery.refetch()}
            >
              重试
            </Button>
          </div>
        </div>
      </main>
    );
  }

  const detail = detailQuery.data;
  const companyName = detail.assessment.company_name;
  const canvasDiagnosis = detail.canvas_diagnosis;
  const hasSavedScoring = savedScoringQuery.data?.scoring_result ?? null;
  const detailPaymentRequired = isPaymentRequired(detail.entitlement);

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8">
        <section className="page-header">
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Link href="/" className="btn-secondary text-xs">
                返回首页
              </Link>
              <Link
                href={`/assessment/${assessmentId}`}
                className="btn-secondary text-xs"
              >
                返回主流程工作台
              </Link>
            </div>
            <span className="badge badge-accent">BMC 三维突破要素评分</span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text sm:text-5xl">
              {companyName} · 突破要素评分矩阵
            </h1>
            <p className="text-base leading-7 text-warm-secondary">
              通过三维评分模型评估九个商业画布模块的突破优先级。
              <strong>痛点迫切度（Pain）</strong> 用于判断问题紧迫性；
              <strong>数据基础度（Data）</strong> 用于判断 AI 模型能否训练落地；
              <strong>实施可行度（Feasibility）</strong> 用于判断组织和资源是否支撑推进。
            </p>
          </div>
        </section>

        {detailPaymentRequired ? (
          <PaymentUnlockPanel
            assessmentId={assessmentId}
            entitlement={detail.entitlement}
            onUnlocked={() => detailQuery.refetch()}
          />
        ) : !canvasDiagnosis ? (
          <div className="card-inset">
            <p className="section-label">画布诊断</p>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              尚未生成商业画布诊断。请先完成企业画像和商业画布诊断后再进行突破要素评分。
            </p>
            <Link
              href={`/assessment/${assessmentId}`}
              className="mt-3 inline-block btn-primary text-xs"
            >
              返回主流程工作台
            </Link>
          </div>
        ) : (
          <BmcScoringMatrix
            key={savedScoringQuery.data?.updated_at ?? "new"}
            assessmentId={assessmentId}
            existingScoring={hasSavedScoring}
            savedSelectedKeys={savedScoringQuery.data?.selected_keys}
            canvasDiagnosis={canvasDiagnosis}
          />
        )}

        <section className="card">
          <p className="section-label">下一步</p>
          <h2 className="section-heading">创新方向候选</h2>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">
            {hasBreakthrough
              ? "突破要素已保存，下一步生成创新方向候选池并确认方向。"
              : "请先保存至少 1 个突破要素（最多 3 个），再生成创新方向候选池。"}
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              onClick={handleGenerateDirections}
              disabled={!hasBreakthrough || expandDirections.isPending}
              loading={expandDirections.isPending}
            >
              {expandDirections.isPending
                ? "生成中..."
                : "生成创新方向候选"}
            </Button>
            {expandDirections.isPending ? <GenerationWaitHint label="正在生成创新方向候选" /> : null}
          </div>
        </section>
      </div>

      <SyncFeedbackPanel assessmentId={assessmentId} />
    </main>
  );
}
