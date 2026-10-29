"use client";

import React, { useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAssessmentDetail } from "@/hooks";
import { useGenerateCompetitiveness } from "@/hooks/use-competitiveness";
import { Button } from "@/components/ui/button";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import { Skeleton } from "@/components/ui/skeleton";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { ScenarioQuadrantView } from "@/components/scenario-quadrant-view";
import { SyncFeedbackPanel } from "@/components/sync-feedback-panel";
import { GenerationMetadata } from "@/components/generation-metadata";
import { toast } from "@/hooks/use-toast";
import { formatMutationError } from "@/lib/api";
import { isPaymentRequired } from "@/lib/payment-entitlement";

export function ScenariosPageContent({
  assessmentId,
}: {
  assessmentId: string;
}) {
  const detailQuery = useAssessmentDetail(assessmentId);
  const router = useRouter();
  const generateCompetitiveness = useGenerateCompetitiveness();

  const handleGenerateCompetitiveness = useCallback(async () => {
    try {
      await generateCompetitiveness.mutateAsync(assessmentId);
      toast({ title: "差异化竞争力报告已生成" });
      router.push(`/assessment/${assessmentId}/competitiveness`);
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "差异化竞争力分析"),
        variant: "destructive",
      });
    }
  }, [assessmentId, generateCompetitiveness, router]);

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
  const industry = detail.assessment.industry;
  const scenarios = detail.scenario_recommendation;
  const paymentRequired = isPaymentRequired(detail.entitlement);
  const canGenerateCompetitiveness =
    Boolean(scenarios) && !detail.progress.has_competitiveness;

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
            <span className="badge badge-warning">AI 推荐场景</span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text sm:text-5xl">
              {companyName} AI 推荐场景
            </h1>
            {industry ? (
              <p className="text-base leading-7 text-warm-secondary">
                {industry}
              </p>
            ) : null}
          </div>
        </section>

        {paymentRequired ? (
          <PaymentUnlockPanel
            assessmentId={assessmentId}
            entitlement={detail.entitlement}
            onUnlocked={() => detailQuery.refetch()}
          />
        ) : scenarios ? (
          <>
            <GenerationMetadata
              generationMode={scenarios.scoring_method}
              generatedAt={scenarios.updated_at ?? scenarios.created_at}
            />
            <ScenarioQuadrantView
              scenarioRecommendation={scenarios}
              assessmentId={assessmentId}
            />

            {canGenerateCompetitiveness ? (
              <section className="card">
                <p className="section-label">下一步</p>
                <h2 className="section-heading">差异化竞争力分析</h2>
                <p className="mt-2 text-sm leading-7 text-muted-foreground">
                  基于已确认的 Top 3 场景生成差异化竞争力报告，再制定核心竞争力推进策略。
                </p>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Button
                    onClick={handleGenerateCompetitiveness}
                    disabled={generateCompetitiveness.isPending}
                    loading={generateCompetitiveness.isPending}
                  >
                    {generateCompetitiveness.isPending
                      ? "生成中..."
                      : "生成差异化竞争力"}
                  </Button>
                  {generateCompetitiveness.isPending ? <GenerationWaitHint label="正在生成差异化竞争力" /> : null}
                </div>
              </section>
            ) : null}
          </>
        ) : (
          <div className="card-inset">
            <p className="section-label">AI 推荐场景</p>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              尚未生成 AI 推荐场景。请先完成创新方向确认后再查看。
            </p>
            <Link
              href={`/assessment/${assessmentId}`}
              className="mt-3 inline-block btn-primary text-xs"
            >
              返回主流程工作台
            </Link>
          </div>
        )}
      </div>

      <SyncFeedbackPanel assessmentId={assessmentId} />
    </main>
  );
}
