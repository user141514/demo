"use client";

import React from "react";

import type {
  EndgameResponse,
  StrategicPath,
  ThreeStageStrategyStage,
} from "@/lib/types";

/**
 * 根据路径类型返回对应的视觉样式。
 */
const pathTypeColor = (type: string) => {
  if (type === "保守") return "border-green-200 bg-green-50/40";
  if (type === "均衡") return "border-amber-200 bg-amber-50/40";
  return "border-red-200 bg-red-50/40";
};

/**
 * 根据推荐等级返回对应的标签样式。
 */
const recLevelColor = (level: string) => {
  if (level === "推荐") return "badge badge-success";
  if (level === "可选") return "badge badge-warning";
  return "badge badge-muted";
};

/**
 * 展示商业终局结果，并承接三阶段推进策略的最终呈现。
 */
export function EndgamePanel({ data }: { data: EndgameResponse }) {
  const { result } = data;
  const { three_stage_strategy, strategic_paths } = result;

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">推进策略</p>
          <h2 className="section-heading">核心竞争力推进策略</h2>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-warm-border-light bg-warm-inset p-6">
        <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">三阶段推进策略</p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <ThreeStageCard stage={three_stage_strategy.stage_1} />
          <ThreeStageCard stage={three_stage_strategy.stage_2} />
          <ThreeStageCard stage={three_stage_strategy.stage_3} />
        </div>
        {three_stage_strategy.key_risks.length > 0 && (
          <div className="mt-4">
            <p className="text-xs uppercase tracking-[0.14em] text-warm-danger">关键风险</p>
            <ul className="mt-2 space-y-1.5">
              {three_stage_strategy.key_risks.map((risk) => (
                <li key={risk} className="flex items-start gap-2 text-xs leading-5 text-warm-muted">
                  <span className="mt-0.5 flex-shrink-0 text-warm-danger">!</span>
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-6">
        <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">多路径推演（{strategic_paths.length} 种策略）</p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {strategic_paths.map((path, i) => <StrategicPathCard key={i} path={path} />)}
        </div>
      </div>
    </div>
  );
}

/**
 * 展示三阶段推进策略中的单个阶段卡片。
 */
function ThreeStageCard({ stage }: { stage: ThreeStageStrategyStage }) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-surface p-4">
      <p className="text-xs font-semibold text-warm-accent">{stage.title} · {stage.focus}</p>
      <div className="mt-3 space-y-2">
        <div>
          <p className="text-[10px] uppercase text-warm-muted">策略</p>
          <p className="mt-0.5 text-[11px] leading-4 text-warm-secondary">{stage.strategy}</p>
        </div>
        <div>
          <p className="text-[10px] uppercase text-warm-muted">目标</p>
          <p className="mt-0.5 text-[11px] leading-4 text-warm-secondary">{stage.objective}</p>
        </div>
        {stage.key_actions.length > 0 && (
          <div>
            <p className="text-[10px] uppercase text-warm-muted">关键动作</p>
            <ul className="mt-1 space-y-0.5">
              {stage.key_actions.map((action, i) => (
                <li key={i} className="text-[11px] leading-4 text-warm-muted">{i + 1}. {action}</li>
              ))}
            </ul>
          </div>
        )}
        {stage.key_risks.length > 0 && (
          <div>
            <p className="text-[10px] uppercase text-warm-danger">关键风险</p>
            <ul className="mt-1 space-y-0.5">
              {stage.key_risks.map((risk, i) => (
                <li key={i} className="text-[11px] leading-4 text-warm-muted">! {risk}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 展示单条终局路径的关键信息。
 */
function StrategicPathCard({ path }: { path: StrategicPath }) {
  return (
    <div className={`rounded-xl border p-6 ${pathTypeColor(path.path_type)}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-warm-text">{path.path_name}</p>
        <span className={recLevelColor(path.recommendation_level)}>{path.recommendation_level}</span>
      </div>
      <div className="mt-3">
        <p className="text-[10px] uppercase text-warm-muted">推进节奏</p>
        <p className="mt-1 text-[11px] leading-4 text-warm-secondary">{path.execution_rhythm}</p>
      </div>
      <div className="mt-3">
        <p className="text-[10px] uppercase text-warm-muted">里程碑</p>
        <ul className="mt-1.5 space-y-1">
          {path.key_milestones.map((m, i) => <li key={i} className="text-[11px] leading-4 text-warm-muted">&bull; {m}</li>)}
        </ul>
      </div>
      <div className="mt-3">
        <p className="text-[10px] uppercase text-warm-muted">能力前提</p>
        <p className="mt-1 text-[11px] leading-4 text-warm-secondary">{path.capability_requirements}</p>
      </div>
      <div className="mt-3">
        <p className="text-[10px] uppercase text-warm-muted">预期成果</p>
        <p className="mt-1 text-[11px] leading-4 text-warm-text">{path.expected_outcomes}</p>
      </div>
      {path.major_risks.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] uppercase text-warm-danger">主要风险</p>
          <ul className="mt-1.5 space-y-1">
            {path.major_risks.map((r, i) => <li key={i} className="text-[10px] leading-4 text-warm-muted">⚠ {r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
