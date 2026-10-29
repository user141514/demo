"use client";

import React from "react";

import type { CompetitivenessResponse } from "@/lib/types";

type ModuleCard = {
  title: string;
  intro: string;
  fields: Array<{ label: string; value: string }>;
};

export function CompetitivenessPanel({
  data,
  companyName = "企业",
  topScenarioNames = [],
}: {
  data: CompetitivenessResponse;
  companyName?: string;
  topScenarioNames?: string[];
}) {
  const cards = buildModuleCards(data.result, topScenarioNames);

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">差异化竞争力</p>
          <h2 className="section-heading">差异化竞争力策略概要</h2>
        </div>
        <span className="badge badge-accent">卡片式输出</span>
      </div>

      <div className="mt-6 rounded-2xl border border-warm-border-light bg-warm-inset px-6 py-5">
        <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">
          输出文档标题
        </p>
        <p className="mt-3 font-heading text-2xl font-bold text-warm-text">
          《{companyName}·差异化竞争力策略概要》
        </p>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        {cards.map((card) => (
          <article
            key={card.title}
            className="rounded-2xl border border-warm-border-light bg-warm-surface p-6"
          >
            <p className="text-sm font-semibold text-warm-accent">{card.title}</p>
            <p className="mt-3 text-sm leading-7 text-warm-secondary">
              {card.intro}
            </p>
            <div className="mt-4 space-y-3">
              {card.fields.map((field) => (
                <div
                  key={`${card.title}-${field.label}`}
                  className="rounded-xl bg-warm-inset px-4 py-3"
                >
                  <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">
                    {field.label}
                  </p>
                  <p className="mt-1 text-sm leading-7 text-warm-text">
                    {field.value}
                  </p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function buildModuleCards(
  result: CompetitivenessResponse["result"],
  topScenarioNames: string[],
): ModuleCard[] {
  const scenarios =
    topScenarioNames.length > 0 ? topScenarioNames : collectPointTitles(result);

  return [
    {
      title: "① AI 点优势串联",
      intro: `将选定的 Top 3 AI 场景（${joinOrFallback(scenarios)}）串联为系统性方案命名。`,
      fields: [
        {
          label: "系统方案名称",
          value: buildSystemSolutionName(result, scenarios),
        },
      ],
    },
    {
      title: "② VP 重构输出",
      intro: "基于 AI 系统方案，重构价值主张（VP）。",
      fields: [
        {
          label: "旧 VP",
          value: result.vp_reconstruction.current_vp,
        },
        {
          label: "新 VP（AI 重构）",
          value: result.vp_reconstruction.enhanced_vp,
        },
      ],
    },
    {
      title: "③ 竞争优势差异化定位",
      intro: "与行业竞争对手的差异化优势描述。",
      fields: [
        {
          label: "差异化优势描述",
          value: buildDifferentiationOverview(result),
        },
        {
          label: "差异化定位语",
          value: buildDifferentiationPositioning(result),
        },
        {
          label: "AI 原生竞争者的威胁应对策略",
          value: buildAiNativeThreatResponse(result),
        },
      ],
    },
    {
      title: "④ 核心竞争力提升路径",
      intro: "3 个阶段的竞争力提升路径（短中长期）。",
      fields: [
        {
          label: "短期",
          value: result.delivery_strategy.phase_1_quick_win,
        },
        {
          label: "中期",
          value: result.delivery_strategy.phase_2_scale,
        },
        {
          label: "长期",
          value: result.delivery_strategy.phase_3_moat,
        },
      ],
    },
  ];
}

function buildSystemSolutionName(
  result: CompetitivenessResponse["result"],
  topScenarioNames: string[],
): string {
  const connections = result.connections.slice(0, 2);
  if (connections.length > 0) {
    const primary = stripLineSuffix(connections[0].line_name);
    if (connections.length > 1) {
      const secondary = stripLineSuffix(connections[1].line_name);
      if (secondary && secondary !== primary) {
        return `${primary}×${secondary}智能协同系统`;
      }
    }
    return `${primary}智能协同系统`;
  }
  if (topScenarioNames.length > 0) {
    return `${topScenarioNames[0]}智能协同系统`;
  }
  return "AI 差异化竞争力协同系统";
}

function buildSynergyDescription(
  result: CompetitivenessResponse["result"],
): string {
  const parts = result.connections
    .slice(0, 3)
    .map((connection) => {
      const pointTitles = joinOrFallback(connection.point_titles);
      return `${pointTitles}共同支撑${connection.line_name}，带来${connection.competitive_impact || "竞争力增益"}`;
    })
    .filter(Boolean);
  return parts.join("；") || result.overall_narrative;
}

function buildDifferentiationOverview(
  result: CompetitivenessResponse["result"],
): string {
  return result.overall_narrative?.trim() || buildDifferentiationPositioning(result);
}

function buildDifferentiationPositioning(
  result: CompetitivenessResponse["result"],
): string {
  const advantages = result.advantages
    .slice(0, 2)
    .map((item) => item.advantage_name);
  return `围绕“${result.vp_reconstruction.enhanced_vp}”，以${joinOrFallback(advantages)}构建不可替代的客户价值定位。`;
}

function buildAiNativeThreatResponse(
  result: CompetitivenessResponse["result"],
): string {
  const lines = result.connections.slice(0, 2).map((item) => item.line_name);
  return `不与 AI 原生竞争者单纯比拼模型能力，而是围绕${joinOrFallback(lines)}，将客户数据、业务流程与专业知识整合为可持续的组织能力。`;
}

function collectPointTitles(result: CompetitivenessResponse["result"]): string[] {
  return result.connections
    .flatMap((item) => item.point_titles)
    .filter((value, index, self) => Boolean(value) && self.indexOf(value) === index)
    .slice(0, 3);
}

function joinOrFallback(values: string[]): string {
  const filtered = values.map((item) => item.trim()).filter(Boolean);
  return filtered.length > 0 ? filtered.join("、") : "当前已选 AI 方向";
}

function stripLineSuffix(value: string): string {
  return value.replace(/线$/, "").trim() || value;
}
