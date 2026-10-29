"use client";

import React, { use, useCallback, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAssessmentDetail, useUpdateEndgame } from "@/hooks";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EndgamePanel } from "@/components/endgame-panel";
import { EndgameEditor } from "@/components/endgame-editor";
import { PaymentUnlockPanel } from "@/components/payment-unlock-panel";
import { SyncFeedbackPanel } from "@/components/sync-feedback-panel";
import { GenerationMetadata } from "@/components/generation-metadata";
import { toast } from "@/hooks/use-toast";
import { formatMutationError } from "@/lib/api";
import { isPaymentRequired } from "@/lib/payment-entitlement";
import type { UpdateEndgamePayload } from "@/lib/types";

export default function EndgamePage({
  params,
}: {
  params: Promise<{ assessmentId: string }>;
}) {
  const { assessmentId } = use(params);
  const router = useRouter();
  const detailQuery = useAssessmentDetail(assessmentId);
  const updateEndgame = useUpdateEndgame();
  const [isEditing, setIsEditing] = useState(false);

  const handleSaveEndgame = useCallback(
    async (payload: UpdateEndgamePayload) => {
      try {
        await updateEndgame.mutateAsync({
          assessmentId,
          payload,
        });
        toast({
          title: "核心竞争力推进策略已更新",
          description: "综合报告已自动失效，请重新生成最终报告。",
        });
        setIsEditing(false);
        await detailQuery.refetch();
      } catch (error) {
        toast({
          title: "保存失败",
          description: formatMutationError(error, "核心竞争力推进策略保存"),
          variant: "destructive",
        });
      }
    },
    [assessmentId, detailQuery, updateEndgame],
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
  const endgameData = detail.endgame;
  const paymentRequired = isPaymentRequired(detail.entitlement);
  const editableEndgame = endgameData
    ? (({ generation_mode: _generationMode, ...rest }) => rest)(endgameData.result)
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
            <span className="badge badge-accent">分阶段推进</span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text sm:text-5xl">
              {companyName} 核心竞争力推进策略
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
        ) : endgameData ? (
          <>
            <GenerationMetadata
              generationMode={endgameData.result.generation_mode}
              generatedAt={endgameData.updated_at ?? endgameData.created_at}
            />
            <div className="flex items-center gap-3">
              <Button
                variant={isEditing ? "default" : "outline"}
                size="sm"
                onClick={() => setIsEditing((current) => !current)}
              >
                {isEditing ? "退出编辑" : "✏️ 手动编辑推进策略"}
              </Button>
              {isEditing ? (
                <span className="text-xs text-warm-accent">
                  编辑模式下可修订三阶段策略和多路径推演。
                </span>
              ) : null}
            </div>

            {isEditing ? (
              <EndgameEditor
                value={editableEndgame!}
                isSaving={updateEndgame.isPending}
                onSave={handleSaveEndgame}
                onCancel={() => setIsEditing(false)}
              />
            ) : (
              <EndgamePanel data={endgameData} />
            )}
          </>
        ) : (
          <div className="card-inset">
            <p className="section-label">核心竞争力推进策略</p>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              尚未生成核心竞争力推进策略。请先完成差异化竞争力分析。
            </p>
            <Link
              href={`/assessment/${assessmentId}/competitiveness`}
              className="mt-3 inline-block btn-primary text-xs"
            >
              前往差异化竞争力页
            </Link>
          </div>
        )}

        <section className="card">
          <p className="section-label">下一步</p>
          <h2 className="section-heading">结果仪表盘</h2>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">
            回到结果仪表盘查看全链路状态，并生成 PDF / Word 导出报告。
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => router.push(`/assessment/${assessmentId}/results`)}>
              查看结果仪表盘
            </Button>
          </div>
        </section>
      </div>

      <SyncFeedbackPanel assessmentId={assessmentId} />
    </main>
  );
}
