"use client";

import React, { useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  useAssessmentDetail,
  useGenerateEndgame,
  useUpdateCompetitiveness,
} from "@/hooks";
import { Button } from "@/components/ui/button";
import { GenerationWaitHint } from "@/components/generation-wait-hint";
import { Skeleton } from "@/components/ui/skeleton";
import { CompetitivenessEditor } from "@/components/competitiveness-editor";
import { CompetitivenessPanel } from "@/components/competitiveness-panel";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { SyncFeedbackPanel } from "@/components/sync-feedback-panel";
import { GenerationMetadata } from "@/components/generation-metadata";
import { toast } from "@/hooks/use-toast";
import { formatMutationError } from "@/lib/api";
import { isPaymentRequired } from "@/lib/payment-entitlement";
import type { UpdateCompetitivenessPayload } from "@/lib/types";

export function CompetitivenessPageContent({
  assessmentId,
}: {
  assessmentId: string;
}) {
  const router = useRouter();
  const detailQuery = useAssessmentDetail(assessmentId);
  const generateEndgame = useGenerateEndgame();
  const updateCompetitiveness = useUpdateCompetitiveness();
  const [isEditing, setIsEditing] = useState(false);

  const handleGenerateEndgame = useCallback(async () => {
    try {
      await generateEndgame.mutateAsync(assessmentId);
      toast({ title: "核心竞争力推进策略已生成" });
      router.push(`/assessment/${assessmentId}/endgame`);
    } catch (error) {
      toast({
        title: "生成失败",
        description: formatMutationError(error, "核心竞争力推进策略"),
        variant: "destructive",
      });
    }
  }, [assessmentId, generateEndgame, router]);

  const handleSaveCompetitiveness = useCallback(
    async (payload: unknown) => {
      try {
        await updateCompetitiveness.mutateAsync({
          assessmentId,
          payload: payload as UpdateCompetitivenessPayload,
        });
        toast({
          title: "差异化竞争力已更新",
          description: "下游终局和综合报告已自动失效，请按顺序重新生成。",
        });
        setIsEditing(false);
        await detailQuery.refetch();
      } catch (error) {
        toast({
          title: "保存失败",
          description: formatMutationError(error, "差异化竞争力保存"),
          variant: "destructive",
        });
      }
    },
    [assessmentId, detailQuery, updateCompetitiveness],
  );

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
  const competitiveness = detail.competitiveness;
  const paymentRequired = isPaymentRequired(detail.entitlement);
  const editableCompetitiveness = competitiveness
    ? (({ generation_mode: _generationMode, ...rest }) => rest)(
        competitiveness.result,
      )
    : null;

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
            <span className="badge badge-warning">差异化竞争力</span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text sm:text-5xl">
              {companyName} 差异化竞争力分析
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
        ) : competitiveness ? (
          <>
            <GenerationMetadata
              generationMode={competitiveness.result.generation_mode}
              generatedAt={competitiveness.updated_at ?? competitiveness.created_at}
            />
            <div className="flex items-center gap-3">
              <Button
                variant={isEditing ? "default" : "outline"}
                size="sm"
                onClick={() => setIsEditing((current) => !current)}
              >
                {isEditing ? "退出编辑" : "✏️ 手动编辑竞争力报告"}
              </Button>
              {isEditing ? (
                <span className="text-xs text-warm-accent">
                  编辑模式下可直接修订系统方案命名、VP 重构、差异化定位和竞争力提升路径。
                </span>
              ) : null}
            </div>

            {isEditing ? (
              <CompetitivenessEditor
                value={editableCompetitiveness!}
                isSaving={updateCompetitiveness.isPending}
                onSave={handleSaveCompetitiveness}
                onCancel={() => setIsEditing(false)}
              />
            ) : (
              <CompetitivenessPanel
                data={competitiveness}
                companyName={companyName}
                topScenarioNames={(detail.scenario_recommendation?.top_scenarios ?? [])
                  .slice(0, 3)
                  .map((item) => item.name)}
              />
            )}

            <section className="card">
              <p className="section-label">下一步</p>
              <h2 className="section-heading">核心竞争力推进策略</h2>
              <p className="mt-2 text-sm leading-7 text-muted-foreground">
                基于当前竞争力结构，生成三阶段推进策略与多路径实施方案。
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  onClick={handleGenerateEndgame}
                  disabled={generateEndgame.isPending}
                  loading={generateEndgame.isPending}
                >
                  {generateEndgame.isPending
                    ? "生成中..."
                    : "生成核心竞争力推进策略"}
                </Button>
                {generateEndgame.isPending ? <GenerationWaitHint label="正在生成核心竞争力推进策略" /> : null}
              </div>
            </section>
          </>
        ) : (
          <div className="card-inset">
            <p className="section-label">差异化竞争力</p>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              尚未生成差异化竞争力分析。请先完成候选场景与 Top 3 场景确认。
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
