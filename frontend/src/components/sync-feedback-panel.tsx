"use client";

import React from "react";
import { useMemo, useState } from "react";

import { useAssessmentDetail } from "@/hooks";

type StepStatus = {
  key: string;
  label: string;
  exists: boolean;
  detail: string;
};

export function SyncFeedbackPanel({ assessmentId }: { assessmentId: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const detailQuery = useAssessmentDetail(assessmentId);
  const data = detailQuery.data;

  const steps = useMemo<StepStatus[]>(() => {
    if (!data) {
      return [];
    }

    return [
      {
        key: "profile",
        label: "企业画像",
        exists: data.progress.has_profile,
        detail: data.progress.has_profile ? "已生成画像内容" : "无结果",
      },
      {
        key: "canvas",
        label: "商业画布",
        exists: data.progress.has_canvas,
        detail: data.progress.has_canvas ? "已生成 9 格诊断" : "无结果",
      },
      {
        key: "breakthrough",
        label: "突破要素",
        exists: data.progress.has_breakthrough,
        detail:
          data.breakthrough_selection && data.breakthrough_selection.length > 0
            ? `已确认 ${data.breakthrough_selection.length} 个突破要素`
            : "无结果",
      },
      {
        key: "directions",
        label: "创新方向",
        exists: data.progress.has_directions,
        detail:
          data.direction_selection?.selected_directions.length
            ? `已确认 ${data.direction_selection.selected_directions.length} 个方向`
            : data.direction_expansion
              ? "已有候选，待确认"
              : "无结果",
      },
      {
        key: "scenarios",
        label: "AI 推荐场景",
        exists: data.progress.has_scenarios,
        detail:
          data.scenario_recommendation?.top_scenarios.length
            ? `已生成 Top ${data.scenario_recommendation.top_scenarios.length}`
            : "无结果",
      },
      {
        key: "competitiveness",
        label: "差异化竞争力",
        exists: data.progress.has_competitiveness,
        detail: data.progress.has_competitiveness ? "已生成竞争力报告" : "无结果",
      },
      {
        key: "endgame",
        label: "推进策略",
        exists: data.progress.has_endgame,
        detail: data.progress.has_endgame ? "已生成核心竞争力推进策略" : "无结果",
      },
      {
        key: "report",
        label: "综合报告",
        exists: data.progress.has_report,
        detail: data.progress.has_report ? "已生成导出报告" : "无结果",
      },
    ];
  }, [data]);

  if (!data || steps.length === 0) {
    return null;
  }

  const readyCount = steps.filter((item) => item.exists).length;

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {isOpen ? (
        <div className="w-80 rounded-xl border border-warm-border-light bg-warm-surface shadow-2xl">
          <div className="flex items-center justify-between border-b border-warm-border-light p-4">
            <div>
              <p className="text-sm font-semibold text-warm-text">同步状态</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {readyCount} / {steps.length} 已完成
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-xs text-muted-foreground hover:text-warm-text"
            >
              关闭
            </button>
          </div>

          <div className="max-h-96 space-y-2 overflow-y-auto p-4">
            {steps.map((step) => (
              <div
                key={step.key}
                className={`rounded-lg border p-3 text-xs ${
                  step.exists
                    ? "border-green-200 bg-green-50/70"
                    : "border-warm-border-light bg-muted/40"
                }`}
              >
                <p className={`font-medium ${step.exists ? "text-warm-success" : "text-muted-foreground"}`}>
                  {step.exists ? "已完成" : "未完成"} · {step.label}
                </p>
                <p className="mt-1 text-[11px] text-muted-foreground">{step.detail}</p>
              </div>
            ))}

            <button
              type="button"
              onClick={() => detailQuery.refetch()}
              className="mt-2 w-full rounded-lg border border-warm-accent/30 bg-warm-accent/5 py-2 text-xs text-warm-accent transition hover:bg-warm-accent/10"
            >
              刷新同步状态
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="rounded-full bg-warm-accent px-4 py-2 text-xs font-semibold text-white shadow-lg transition hover:bg-warm-accent/90"
        >
          同步状态 {readyCount}/{steps.length}
        </button>
      )}
    </div>
  );
}
