"use client";

import type { AssessmentBreakthroughResponse, BreakthroughElement } from "@/lib/types";

const scoreColor = (score: number): string => {
  if (score >= 70) return "text-green-700 bg-green-100";       // 🟢 绿色
  if (score >= 50) return "text-yellow-700 bg-yellow-100";     // 🟡 黄色
  return "text-red-700 bg-red-100";                              // 🔴 红色
};

const sourceLabel = (score: number): string => {
  if (score >= 70) return "🚀 建议突破";
  if (score >= 50) return "📋 可考虑";
  return "⏸ 暂缓";
};

export function BreakthroughSelectionPanel({
  data, selectedKeys, isSelecting, onToggleElement, onConfirmSelection,
}: {
  data: AssessmentBreakthroughResponse;
  selectedKeys: string[];
  isSelecting: boolean;
  onToggleElement: (key: string) => void;
  onConfirmSelection: () => void;
}) {
  const { breakthrough_recommendation, breakthrough_selection } = data;
  const { elements, recommended_keys, overall_suggestion, generation_mode } = breakthrough_recommendation;
  const sortedElements = [...elements].sort((a, b) => a.score - b.score);
  const hasExistingSelection = breakthrough_selection !== null && breakthrough_selection.selected_elements.length >= 1;

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">突破分析</p>
          <h2 className="section-heading">突破要素选择</h2>
        </div>
        <span className="badge badge-accent">
          {generation_mode === "rule_based" ? "规则评分" : "Mock"}
        </span>
      </div>

      <>
        {hasExistingSelection && (
          <p className="mt-4 text-sm text-warm-success">
            已保存 {breakthrough_selection.selected_elements.length} 个突破要素，可直接重新选择并保存，后续分析将按新选择更新。
          </p>
        )}
          <div className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-start">
            <div className="flex-1 rounded-xl border border-warm-accent/15 bg-warm-accent/5 p-6">
              <p className="text-xs uppercase tracking-[0.14em] text-warm-muted">系统建议</p>
              <p className="mt-3 text-sm leading-7 text-warm-secondary">{overall_suggestion}</p>
              {recommended_keys.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {recommended_keys.map((key) => {
                    const el = elements.find((e) => e.key === key);
                    return <span key={key} className="badge badge-accent">{el?.title ?? key}</span>;
                  })}
                </div>
              )}
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-6 py-4 text-sm text-amber-800 lg:max-w-[220px]">
              <p className="font-medium">选择规则</p>
              <ul className="mt-2 list-inside list-disc space-y-1">
                <li>选择 1–3 个要素</li>
                <li>评分越低，越需要优先突破</li>
                <li>可以采纳系统推荐，也可以手动调整</li>
              </ul>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {sortedElements.map((el) => (
              <ElementCard key={el.key} element={el} isRecommended={recommended_keys.includes(el.key)} isSelected={selectedKeys.includes(el.key)} showToggle onToggle={() => onToggleElement(el.key)} />
            ))}
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button type="button" onClick={onConfirmSelection} disabled={isSelecting || selectedKeys.length < 1 || selectedKeys.length > 3} className="btn-primary">
              {isSelecting ? "保存中..." : selectedKeys.length < 1 ? `请至少选择 1 个要素（已选 ${selectedKeys.length}）` : selectedKeys.length > 3 ? `最多选择 3 个要素（已选 ${selectedKeys.length}）` : `确认选择（${selectedKeys.length} 个要素）`}
            </button>
            <button
              type="button"
              onClickCapture={(e) => {
                e.preventDefault();
                if (!window.confirm("确定要清空已选择的突破要素吗？此操作不可撤销。")) return;
                selectedKeys.forEach((k) => onToggleElement(k));
              }}
              className="btn-secondary"
            >
              清空选择
            </button>
          </div>
      </>
    </div>
  );
}

function ElementCard({ element, isRecommended, isSelected, showToggle, onToggle }: {
  element: BreakthroughElement; isRecommended: boolean; isSelected: boolean; showToggle: boolean; onToggle: () => void;
}) {
  return (
    <button type="button" onClick={onToggle}
      className={`rounded-xl border bg-warm-inset p-6 text-left transition ${
        isSelected ? "border-warm-accent/40 bg-warm-accent/5 ring-1 ring-warm-accent/15" : "border-warm-border-light hover:border-warm-border hover:shadow-card"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-warm-text">{element.title}</p>
            {isRecommended && !isSelected && <span className="badge badge-accent text-xs">推荐</span>}
            {isSelected && <span className="badge badge-success text-xs">已选</span>}
          </div>
          <p className="mt-2 text-xs leading-5 text-warm-muted">{element.reason}</p>
          <p className="mt-2 text-xs leading-5 text-warm-muted">{element.ai_opportunity}</p>
        </div>
        <div className={`flex-shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${scoreColor(element.score)}`}>
          {element.score}
        </div>
      </div>
      <div className="mt-3">
        <span className="text-[11px] uppercase tracking-[0.12em] text-warm-muted">{sourceLabel(element.score)}</span>
      </div>
    </button>
  );
}
