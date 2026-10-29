"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BMC_MODULES } from "@/lib/types";
import type {
  ModuleScoreInput,
  ModuleScoringResult,
  BmcScoringResult,
  BmcScoringZone,
} from "@/lib/types";
import type { CanvasDiagnosisResult } from "@/lib/types";
import {
  useCalculateBMCScoring,
  useSaveBMCScoring,
  useAutoDeriveBMCScoring,
} from "@/hooks/use-bmc-scoring";
import { autoDeriveBMCScoring } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { formatMutationError } from "@/lib/api";

// ── 评分常量（与后端一致） ──

const W_PAIN = 0.4;
const W_DATA = 0.35;
const W_FEAS = 0.25;
const ALPHA = 0.05;
const SCORE_MIN = 1.05;
const SCORE_RANGE = 5.2;

const INTERNAL_EFFICIENCY_KEYS = new Set([
  "key_activities",
  "key_resources",
  "cost_structure",
]);

const MODULE_ABBR_MAP: Record<string, string> = {};
BMC_MODULES.forEach((m) => {
  MODULE_ABBR_MAP[m.key] = m.abbr;
});

// ── 本地计算工具 ──

interface DimScores {
  p: number;
  d: number;
  f: number;
}

function calcScoreLocal(s: DimScores): { raw: number; norm: number } {
  const raw =
    s.p * W_PAIN + s.d * W_DATA + s.f * W_FEAS + s.p * s.d * ALPHA;
  const norm = Math.max(0, Math.min(100, ((raw - SCORE_MIN) / SCORE_RANGE) * 100));
  return {
    raw: Math.round(raw * 100) / 100,
    norm: Math.round(norm * 10) / 10,
  };
}

function getZoneLocal(s: DimScores, norm: number): BmcScoringZone {
  // veto checks
  if (s.f <= 1) return "blocked";
  if (s.d <= 1 && s.p <= 3) return "blocked";
  if (s.p <= 2) return "hold";

  if (s.p >= 4 && s.d >= 4) return "quickwin";
  if (s.p >= 4 && s.d < 4) return "strategic";
  if (s.p < 4 && s.d >= 4) return "longterm";
  return "hold";
}

function getVetoStatusLocal(s: DimScores): { status: string; reason: string | null } {
  if (s.f <= 1)
    return { status: "blocked_feasibility", reason: "存在根本性实施障碍，建议 12 个月后重新评估。" };
  if (s.d <= 1 && s.p <= 3)
    return { status: "blocked_data_pain", reason: "数据空白且痛点不严重，AI 投入产出比极低。" };
  if (s.p <= 2)
    return { status: "not_recommended", reason: "痛点不明显，缺乏组织动力，项目极易烂尾。" };
  return { status: "none", reason: null };
}

function getStarsAndLabel(zone: BmcScoringZone, norm: number): { stars: string; label: string } {
  if (zone === "blocked") return { stars: "🚫", label: "一票否决 · 强制暂缓" };
  if (zone === "quickwin") {
    if (norm >= 80) return { stars: "⭐⭐⭐", label: "🚀 最优突破口 · 强烈推荐" };
    if (norm >= 70) return { stars: "⭐⭐⭐", label: "🚀 强烈推荐 · 快赢黄金区" };
    return { stars: "⭐⭐⭐", label: "🚀 推荐 · 快赢黄金区" };
  }
  if (zone === "strategic") {
    if (norm >= 60) return { stars: "⭐⭐", label: "📋 战略布局 · 高优先级" };
    return { stars: "⭐⭐", label: "📋 可考虑 · 战略攻坚区" };
  }
  if (zone === "longterm") {
    if (norm >= 50) return { stars: "⭐", label: "🌱 长期培育 · 数据已就绪" };
    return { stars: "⭐", label: "🌱 低优先级培育" };
  }
  return { stars: "—", label: "⏸ 暂缓 · 当前条件不成熟" };
}

const ZONE_COLORS: Record<BmcScoringZone, string> = {
  quickwin: "#22c55e",   // 🟢 绿色 - 快赢黄金区
  strategic: "#eab308",  // 🟡 黄色 - 战略攻坚区
  longterm: "#3b82f6",   // 🔵 蓝色 - 长效培育区
  hold: "#9ca3af",       // ⚪ 灰色 - 暂缓观望区
  blocked: "#ef4444",    // 🔴 红色 - 否决
};

// ── 组件 Props ──

interface BmcScoringMatrixProps {
  assessmentId: string;
  existingScoring: BmcScoringResult | null;
  savedSelectedKeys?: string[];
  canvasDiagnosis: CanvasDiagnosisResult | null;
}

// ── 组件 ──

export function BmcScoringMatrix({
  assessmentId,
  existingScoring,
  savedSelectedKeys,
  canvasDiagnosis,
}: BmcScoringMatrixProps) {
  // 每个模块的三维评分本地状态
  const [moduleScores, setModuleScores] = useState<Record<string, DimScores>>(() => {
    const init: Record<string, DimScores> = {};
    BMC_MODULES.forEach((m) => {
      // 如果有已有评分数据，从中恢复
      if (existingScoring) {
        const existing = existingScoring.module_results.find((r) => r.key === m.key);
        if (existing) {
          init[m.key] = { p: existing.pain, d: existing.data, f: existing.feasibility };
          return;
        }
      }
      init[m.key] = { p: 3, d: 3, f: 3 };
    });
    return init;
  });

  const [currentModule, setCurrentModule] = useState<string>(BMC_MODULES[0].key);
  const [selectedTopKeys, setSelectedTopKeys] = useState<string[]>(
    () => savedSelectedKeys ?? existingScoring?.top_3_keys ?? [],
  );
  const [showManualSelection, setShowManualSelection] = useState(false);
  const [autoDerivedModules, setAutoDerivedModules] = useState<ModuleScoreInput[] | null>(null);
  // 跟踪保存状态：null=未保存, 'saving'=保存中, 'saved'=已保存, 'error'=保存失败
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  // 保存一份"上次持久化的模块评分快照"，用于检测未保存更改
  const [lastPersistedScores, setLastPersistedScores] = useState<Record<string, DimScores> | null>(() => {
    if (existingScoring) {
      const snap: Record<string, DimScores> = {};
      existingScoring.module_results.forEach((r) => {
        snap[r.key] = { p: r.pain, d: r.data, f: r.feasibility };
      });
      return snap;
    }
    // Default scores (3,3,3) are the "clean" initial state — not a change
    const defaults: Record<string, DimScores> = {};
    BMC_MODULES.forEach((m) => { defaults[m.key] = { p: 3, d: 3, f: 3 }; });
    return defaults;
  });

  const canvasRef = useRef<HTMLCanvasElement>(null);

  // ── 派生状态：是否有未保存的修改 ──
  const hasUnsavedChanges = useMemo(() => {
    if (!lastPersistedScores) return true; // never saved
    for (const m of BMC_MODULES) {
      const cur = moduleScores[m.key];
      const last = lastPersistedScores[m.key];
      if (!last || cur.p !== last.p || cur.d !== last.d || cur.f !== last.f) return true;
    }
    return false;
  }, [moduleScores, lastPersistedScores]);

  // 当滑块被调整时，reset saveState
  const updateScoreWithDirty = (key: string, dim: "p" | "d" | "f", value: number) => {
    if (saveState === "saved") setSaveState("idle");
    setModuleScores((prev) => ({
      ...prev,
      [key]: { ...prev[key], [dim]: value },
    }));
  };

  // ── 实时本地计算 ──

  const localScoreMap = useMemo(() => {
    const map: Record<string, ModuleScoringResult> = {};
    BMC_MODULES.forEach((m) => {
      const s = moduleScores[m.key];
      const { raw, norm } = calcScoreLocal(s);
      const zone = getZoneLocal(s, norm);
      const veto = getVetoStatusLocal(s);
      const meta = getStarsAndLabel(zone, norm);
      map[m.key] = {
        key: m.key,
        title: m.title,
        abbr: m.abbr,
        category: m.category,
        pain: s.p,
        data: s.d,
        feasibility: s.f,
        raw_score: raw,
        normalized_score: norm,
        zone,
        veto_status: veto.status,
        veto_reason: veto.reason,
        recommendation_level:
          zone === "blocked" ? "veto" : zone === "quickwin" ? "top" : zone === "strategic" ? "strategic" : zone === "longterm" ? "cultivate" : "none",
        recommendation_label: meta.label,
        recommendation_stars: meta.stars,
      };
    });
    return map;
  }, [moduleScores]);

  // 本地 Top 3
  const localTop3 = useMemo(
    () => Object.values(localScoreMap)
      .sort((a, b) => b.normalized_score - a.normalized_score)
      .slice(0, 3),
    [localScoreMap],
  );

  // 互补性警告
  const complementarityWarning = useMemo(() => {
    if (selectedTopKeys.length === 3 && selectedTopKeys.every((k) => INTERNAL_EFFICIENCY_KEYS.has(k))) {
      return "您当前选择的突破要素全部集中在内部效率优化（KA/KR/C$），建议考虑增加一个市场侧要素（CS/VP/CH/CR），以形成'内外兼修'的创新组合。";
    }
    return null;
  }, [selectedTopKeys]);

  const currentResult = localScoreMap[currentModule];

  // ── Canvas 绘制四象限矩阵 ──

  const drawMatrix = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const pad = { l: 50, r: 20, t: 30, b: 50 };
    const iW = W - pad.l - pad.r;
    const iH = H - pad.t - pad.b;

    ctx.clearRect(0, 0, W, H);

    // 四象限背景
    const quads = [
      { x: 0, y: 0, color: "#fff3e8", label: "② 战略攻坚区" },
      { x: 0.5, y: 0, color: "#eaf3e0", label: "① 快赢黄金区" },
      { x: 0, y: 0.5, color: "#f0f0f0", label: "④ 暂缓观望区" },
      { x: 0.5, y: 0.5, color: "#e8f0f8", label: "③ 长效培育区" },
    ];
    quads.forEach((q) => {
      const qx = pad.l + q.x * iW;
      const qy = pad.t + q.y * iH;
      ctx.fillStyle = q.color;
      ctx.fillRect(qx, qy, 0.5 * iW, 0.5 * iH);

      ctx.fillStyle = "rgba(0,0,0,0.16)";
      ctx.font = "11px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(q.label, qx + 0.5 * iW * 0.5, qy + 0.5 * iH * 0.5 + 4);
    });

    // 网格线 (虚线)
    ctx.strokeStyle = "#d8d0c4";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.l + iW * 0.5, pad.t);
    ctx.lineTo(pad.l + iW * 0.5, pad.t + iH);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(pad.l, pad.t + iH * 0.5);
    ctx.lineTo(pad.l + iW, pad.t + iH * 0.5);
    ctx.stroke();
    ctx.setLineDash([]);

    // 坐标轴
    ctx.strokeStyle = "#a0978a";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(pad.l, pad.t);
    ctx.lineTo(pad.l, pad.t + iH);
    ctx.lineTo(pad.l + iW, pad.t + iH);
    ctx.stroke();

    // 轴标签
    ctx.fillStyle = "#7a7a7a";
    ctx.font = "bold 11px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("← 数据薄弱          数据充足 →", pad.l + iW / 2, pad.t + iH + 36);

    ctx.save();
    ctx.translate(14, pad.t + iH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("← 痛点一般          痛点迫切 →", 0, 0);
    ctx.restore();

    // 刻度
    ctx.font = "10px sans-serif";
    ctx.fillStyle = "#a0978a";
    ctx.textAlign = "center";
    [1, 2, 3, 4, 5].forEach((v) => {
      const x = pad.l + ((v - 1) / 4) * iW;
      ctx.fillText(String(v), x, pad.t + iH + 14);
    });
    ctx.textAlign = "right";
    [1, 2, 3, 4, 5].forEach((v) => {
      const y = pad.t + iH - ((v - 1) / 4) * iH;
      ctx.fillText(String(v), pad.l - 6, y + 4);
    });

    // 绘制所有模块气泡
    BMC_MODULES.forEach((m) => {
      const s = moduleScores[m.key];
      const res = localScoreMap[m.key];
      const zone = res.zone;
      const color = ZONE_COLORS[zone] || "#909090";

      const cx = pad.l + ((s.d - 1) / 4) * iW;
      const cy = pad.t + iH - ((s.p - 1) / 4) * iH;
      const r = 8 + s.f * 3;

      const isCurrent = m.key === currentModule;

      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = color + (isCurrent ? "ff" : "99");
      ctx.fill();
      if (isCurrent) {
        ctx.strokeStyle = "#2c2c2c";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      ctx.fillStyle = isCurrent ? "#fff" : "rgba(255,255,255,0.9)";
      ctx.font = `bold ${isCurrent ? 11 : 9}px sans-serif`;
      ctx.textAlign = "center";
      ctx.fillText(m.abbr, cx, cy + 4);
    });

    // 当前模块分数标注
    const curS = moduleScores[currentModule];
    const curR = localScoreMap[currentModule];
    if (curR) {
      const cx = pad.l + ((curS.d - 1) / 4) * iW;
      const cy = pad.t + iH - ((curS.p - 1) / 4) * iH;
      ctx.fillStyle = "#2c2c2c";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = cx > pad.l + iW * 0.7 ? "right" : "left";
      const tx = cx > pad.l + iW * 0.7 ? cx - 18 : cx + 18;
      ctx.fillText(`${curR.normalized_score.toFixed(0)}分`, tx, cy - 14);
    }
  }, [moduleScores, currentModule, localScoreMap]);

  // 响应性绘制
  useEffect(() => {
    drawMatrix();
  }, [drawMatrix]);

  // ── 滑块事件处理 ──

  function updateScore(key: string, dim: "p" | "d" | "f", value: number) {
    setModuleScores((prev) => ({
      ...prev,
      [key]: { ...prev[key], [dim]: value },
    }));
  }

  function handleSwitchModule(key: string) {
    setCurrentModule(key);
  }

  function handleToggleSelection(key: string) {
    if (saveState === "saved") setSaveState("idle");
    setSelectedTopKeys((prev) => {
      if (prev.includes(key)) {
        return prev.filter((k) => k !== key);
      }
      if (prev.length >= 3) {
        const dropped = prev[0]; // 最早选择的被替换
        toast({
          title: `已替换为「${MODULE_ABBR_MAP[key] || key}」`,
          description: `已移除「${MODULE_ABBR_MAP[dropped] || dropped}」，最多选择 3 个突破要素。`,
        });
        return [...prev.slice(1), key];
      }
      return [...prev, key];
    });
  }

  // ── 首次加载自动推导 ──

  const [initialAutoDeriveDone, setInitialAutoDeriveDone] = useState(false);

  useEffect(() => {
    // 只在没有已保存评分 + 有画布诊断 + 尚未自动推导时触发
    if (!existingScoring && canvasDiagnosis && !initialAutoDeriveDone) {
      setInitialAutoDeriveDone(true);
      // 异步触发自动推导，不阻塞首次渲染
      const doAutoDerive = async () => {
        try {
          const result = await autoDeriveBMCScoring(assessmentId);
          const newScores: Record<string, DimScores> = {};
          result.modules.forEach((m) => {
            newScores[m.key] = { p: m.pain, d: m.data, f: m.feasibility };
          });
          setModuleScores(newScores);
          setAutoDerivedModules(result.modules);
        } catch {
          // 自动推导失败静默处理，用户可手动点击按钮
        }
      };
      doAutoDerive();
    }
  }, [existingScoring, canvasDiagnosis, initialAutoDeriveDone, assessmentId]);

  // ── API 调用 ──

  const autoDeriveMutation = useAutoDeriveBMCScoring();
  const saveMutation = useSaveBMCScoring();

  // 保存自动推导前的手动调整用于撤销
  const [preDeriveScores, setPreDeriveScores] = useState<Record<string, DimScores> | null>(null);

  async function handleAutoDerive() {
    // 逻辑层守卫：防止重复提交
    if (autoDeriveMutation.isPending) return;

    // 如果用户已做手动调整，确认是否覆盖
    if (hasUnsavedChanges && !autoDerivedModules) {
      const confirmed = window.confirm(
        "自动推导将覆盖您当前的所有手动评分调整，是否继续？\n\n" +
        "点击「确定」将从画布诊断重新推导初始评分。\n" +
        "点击「取消」保留当前手动评分。"
      );
      if (!confirmed) return;
    }

    // 保存当前评分用于撤销
    setPreDeriveScores({ ...moduleScores });

    try {
      const result = await autoDeriveMutation.mutateAsync(assessmentId);
      const newScores: Record<string, DimScores> = {};
      result.modules.forEach((m) => {
        newScores[m.key] = { p: m.pain, d: m.data, f: m.feasibility };
      });
      setModuleScores(newScores);
      setAutoDerivedModules(result.modules);
      setSaveState("idle");
      setLastPersistedScores(null);
      toast({
        title: "已从画布诊断自动推导初始评分",
        description: preDeriveScores ? "可点击「撤销推导」恢复之前的手动调整" : undefined,
      });
    } catch (e) {
      toast({ title: "自动推导失败", description: formatMutationError(e, "请确认画布诊断已生成"), variant: "destructive" });
    }
  }

  function handleUndoAutoDerive() {
    if (!preDeriveScores) return;
    setModuleScores(preDeriveScores);
    setPreDeriveScores(null);
    setAutoDerivedModules(null);
    setSaveState("idle");
    toast({ title: "已恢复手动评分", description: "自动推导的评分已撤销。" });
  }

  async function handleSave() {
    // 逻辑层守卫：防止重复提交
    if (saveMutation.isPending) return;

    if (selectedTopKeys.length < 1) {
      toast({ title: "请至少选择 1 个突破要素", variant: "destructive" });
      return;
    }

    const allScores: ModuleScoreInput[] = Object.entries(moduleScores).map(([key, s]) => ({
      key,
      pain: s.p,
      data: s.d,
      feasibility: s.f,
    }));

    setSaveState("saving");
    try {
      await saveMutation.mutateAsync({
        assessmentId,
        payload: {
          selected_keys: selectedTopKeys,
          all_module_scores: allScores,
          selection_mode: "bmc_scoring",
        },
      });
      // 保存当前评分快照用于 dirty 检测
      setLastPersistedScores({ ...moduleScores });
      setSaveState("saved");
      setPreDeriveScores(null); // 清除撤销记录
      toast({
        title: "评分已保存，突破要素已锁定",
        description: `已选择 ${selectedTopKeys.length} 个突破要素（${selectedTopKeys.map((k) => MODULE_ABBR_MAP[k] || k).join("、")}），下游流程将基于此选择。`,
      });
    } catch (e) {
      setSaveState("error");
      toast({ title: "保存失败", description: formatMutationError(e, "请重试"), variant: "destructive" });
    }
  }

  // ── 渲染 ──

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      {/* LEFT: 控制面板 */}
      <section className="card">
        <div className="section-label">📐 评分参数配置</div>

        {/* 模块选择器 */}
        <div className="mt-3 text-xs text-muted-foreground font-semibold">
          选择要评估的画布模块：
        </div>
        <div className="mt-2 grid grid-cols-3 gap-1.5">
          {BMC_MODULES.map((m) => (
            <button
              key={m.key}
              onClick={() => handleSwitchModule(m.key)}
              className={`rounded-lg border-2 px-2 py-1.5 text-center text-xs font-semibold transition ${
                m.key === currentModule
                  ? "border-warm-accent bg-warm-accent/10 text-warm-accent"
                  : "border-warm-border bg-warm-surface text-muted-foreground hover:border-warm-accent/50"
              }`}
            >
              <span className="block text-[10px] font-normal text-muted-foreground">{m.abbr}</span>
              {m.title}
            </button>
          ))}
        </div>

        <div className="mt-4 border-t border-warm-border" />

        {/* 三维滑块 */}
        <div className="mt-3 text-xs text-muted-foreground font-semibold">
          调整三维评分（1–5 分，步长 0.5）：
        </div>

        {/* Pain */}
        <DimSlider
          label="痛点迫切度 (Pain)"
          emoji="🔴"
          value={moduleScores[currentModule]?.p ?? 3}
          onChange={(v) => updateScoreWithDirty(currentModule, "p", v)}
          labels={["1·无痛点", "3·中度", "5·生死攸关"]}
        />

        {/* Data */}
        <DimSlider
          label="数据基础度 (Data)"
          emoji="💎"
          value={moduleScores[currentModule]?.d ?? 3}
          onChange={(v) => updateScoreWithDirty(currentModule, "d", v)}
          labels={["1·无数据", "3·基础", "5·数据金矿"]}
        />

        {/* Feasibility */}
        <DimSlider
          label="实施可行度 (Feasibility)"
          emoji="🚀"
          value={moduleScores[currentModule]?.f ?? 3}
          onChange={(v) => updateScoreWithDirty(currentModule, "f", v)}
          labels={["1·不可行", "3·需准备", "5·随时启动"]}
        />

        {/* Veto 警告 */}
        {currentResult && currentResult.veto_status === "blocked_feasibility" && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600">
            🚫 <strong>一票否决：</strong>实施可行度 = 1，存在根本性障碍，强制暂缓
          </div>
        )}
        {currentResult && currentResult.veto_status === "blocked_data_pain" && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
            ⚠️ <strong>一票否决：</strong>数据空白且痛点不严重，AI 投入产出比极低
          </div>
        )}
        {currentResult && currentResult.veto_status === "not_recommended" && (
          <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-600">
            💡 <strong>痛点不足：</strong>痛点迫切度 ≤ 2，组织缺乏改变动力，不推荐
          </div>
        )}

        {/* 结果卡片 */}
        {currentResult && (
          <div className="mt-4 rounded-xl border-2 border-warm-border p-4">
            <div className="flex justify-between items-center">
              <span className="text-xs text-muted-foreground">原始优先级得分</span>
              <span className="text-lg font-bold text-warm-accent">{currentResult.raw_score.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-xs text-muted-foreground">归一化总分（/100）</span>
              <span className="text-2xl font-extrabold">{currentResult.normalized_score.toFixed(1)}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-xs text-muted-foreground">推荐等级</span>
              <span className="text-base">{currentResult.recommendation_stars}</span>
            </div>
            <div
              className="mt-3 rounded-lg px-3 py-2 text-center text-sm font-bold"
              style={{
                backgroundColor: ZONE_COLORS[currentResult.zone] + "20",
                color: ZONE_COLORS[currentResult.zone],
              }}
            >
              {currentResult.recommendation_label}
            </div>
          </div>
        )}

        {/* 公式展示 */}
        <div className="mt-3 rounded-lg bg-warm-inset p-3 text-[11px] text-muted-foreground font-mono leading-relaxed">
          {(() => {
            const s = moduleScores[currentModule];
            if (!s) return null;
            const p1 = (s.p * W_PAIN).toFixed(3);
            const p2 = (s.d * W_DATA).toFixed(3);
            const p3 = (s.f * W_FEAS).toFixed(3);
            const p4 = (s.p * s.d * ALPHA).toFixed(3);
            const { raw, norm } = calcScoreLocal(s);
            return (
              <>
                Score = ({s.p}×0.40) + ({s.d}×0.35) + ({s.f}×0.25) + ({s.p}×{s.d}×0.05)
                <br />
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;= {p1} + {p2} + {p3} + {p4} = <strong className="text-warm-accent">{raw.toFixed(2)}</strong>
                <br />
                Norm = ({raw.toFixed(2)} − 1.05) / 5.20 × 100 = <strong className="text-warm-accent">{norm.toFixed(1)} 分</strong>
              </>
            );
          })()}
        </div>

        {/* 自动推导按钮 */}
        <div className="mt-3 space-y-1.5">
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            onClick={handleAutoDerive}
            disabled={autoDeriveMutation.isPending || !canvasDiagnosis}
          >
            {autoDeriveMutation.isPending ? "推导中..." : "🤖 从画布诊断自动推导初始评分"}
          </Button>
          {preDeriveScores && (
            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={handleUndoAutoDerive}
            >
              ↩ 撤销推导，恢复手动评分
            </Button>
          )}
        </div>
      </section>

      {/* RIGHT: 可视化面板 */}
      <section className="flex flex-col gap-4">
        {/* 四象限矩阵 */}
        <div className="card">
          <div className="section-label mb-3">📊 优先级四象限矩阵</div>
          <div className="flex justify-center">
            <canvas ref={canvasRef} id="matrix" width={600} height={360} className="rounded-lg" role="img" aria-label="优先级四象限矩阵：X轴为数据基础度，Y轴为痛点迫切度，气泡大小为实施可行度" />
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#5d8a4a]" /> 快赢黄金区（≥70分）
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#c07020]" /> 战略攻坚区（50-69分）
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#3070a0]" /> 长效培育区（40-59分）
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#909090]" /> 暂缓观望区（{"<"}40分）
            </span>
          </div>
        </div>

        {/* 柱状图：九大模块得分概览 */}
        <div className="card">
          <div className="section-label mb-3">📋 九大模块得分概览</div>
          <div className="space-y-2">
            {Object.entries(localScoreMap)
              .sort(([, a], [, b]) => b.normalized_score - a.normalized_score)
              .map(([key, result]) => {
                const color = ZONE_COLORS[result.zone] || "#909090";
                const isCurrent = key === currentModule;
                return (
                  <div
                    key={key}
                    className="flex items-center gap-2 cursor-pointer rounded px-1 py-0.5 hover:bg-warm-surface"
                    onClick={() => handleSwitchModule(key)}
                  >
                    <span
                      className="w-16 flex-shrink-0 text-[11px] font-semibold"
                      style={{ fontWeight: isCurrent ? 800 : 600, color: isCurrent ? "#2c2c2c" : undefined }}
                    >
                      {MODULE_ABBR_MAP[key]} {result.title}
                    </span>
                    <div className="flex-1 h-5 rounded bg-warm-inset overflow-hidden">
                      <div
                        className="h-full rounded flex items-center justify-end pr-2 transition-all duration-300"
                        style={{
                          width: `${Math.max(result.normalized_score, 4)}%`,
                          backgroundColor: color + (isCurrent ? "" : "99"),
                        }}
                      >
                        <span className="text-[11px] font-bold text-white">
                          {result.normalized_score.toFixed(0)}
                        </span>
                      </div>
                    </div>
                    <span className="w-14 flex-shrink-0 text-right text-[10px] font-semibold" style={{ color }}>
                      {result.recommendation_stars}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Top 3 推荐面板 */}
        <div className="card">
          <div className="section-label mb-3">🎯 Top 3 突破要素推荐</div>
          <p className="text-xs text-muted-foreground mb-3">
            按九大模块得分排序推荐，可选择 1–3 个，也可自由调整
          </p>
          <div className="space-y-2">
            {localTop3.map((result, idx) => {
              const color = ZONE_COLORS[result.zone] || "#909090";
              const isSelected = selectedTopKeys.includes(result.key);
              return (
                <div
                  key={result.key}
                  onClick={() => handleToggleSelection(result.key)}
                  className={`flex items-center gap-3 rounded-lg border-2 p-3 cursor-pointer transition ${
                    isSelected
                      ? "border-warm-accent bg-warm-accent/5"
                      : "border-warm-border hover:border-warm-accent/30"
                  }`}
                >
                  <span className="text-xl font-extrabold text-muted-foreground">#{idx + 1}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="badge-accent text-[10px]">{result.abbr}</span>
                      <span className="text-sm font-semibold">{result.title}</span>
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      痛点 {result.pain}/5 · 数据 {result.data}/5 · 可行度 {result.feasibility}/5
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-lg font-extrabold" style={{ color }}>
                      {result.normalized_score.toFixed(1)}
                    </span>
                    <span className="block text-[10px] text-muted-foreground">{result.recommendation_stars}</span>
                  </div>
                  {isSelected && (
                    <span className="text-warm-accent text-xl">✓</span>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-4">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setShowManualSelection((previous) => !previous)}
              aria-expanded={showManualSelection}
            >
              {showManualSelection ? "收起自定义选择" : "重新调整突破要素（全部九大模块）"}
            </Button>
            {showManualSelection && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {Object.values(localScoreMap)
                  .sort((a, b) => b.normalized_score - a.normalized_score)
                  .map((result) => {
                    const selected = selectedTopKeys.includes(result.key);
                    return (
                      <button
                        key={result.key}
                        type="button"
                        onClick={() => handleToggleSelection(result.key)}
                        aria-pressed={selected}
                        className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-xs transition ${selected ? "border-warm-accent bg-warm-accent/5" : "border-warm-border hover:border-warm-accent/50"}`}
                      >
                        <span>{result.abbr} {result.title}</span>
                        <span className="ml-2 font-bold">{result.normalized_score.toFixed(0)} {selected ? "✓" : ""}</span>
                      </button>
                    );
                  })}
              </div>
            )}
          </div>

          {/* 互补性警告 */}
          {complementarityWarning && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              ⚠️ {complementarityWarning}
            </div>
          )}

          <Button
            className="mt-4 w-full"
            onClick={handleSave}
            disabled={saveMutation.isPending || saveState === "saved" || selectedTopKeys.length < 1}
            variant={saveState === "saved" ? "success" : saveState === "error" ? "destructive" : "default"}
          >
            {saveMutation.isPending
              ? "保存中..."
              : saveState === "saved"
                ? "✓ 已保存并锁定突破要素"
                : saveState === "error"
                  ? "保存失败，点击重试"
                  : `保存并锁定突破要素（已选 ${selectedTopKeys.length}/3）`}
          </Button>

          {/* 未保存更改提示 */}
          {hasUnsavedChanges && saveState !== "saving" && (
            <p className="mt-2 text-center text-[11px] text-amber-600">
              ⚠ 有未保存的评分修改
            </p>
          )}

          {selectedTopKeys.length > 0 && (
            <p className="mt-1 text-center text-[11px] text-muted-foreground">
              已选择：{selectedTopKeys.map((k) => MODULE_ABBR_MAP[k] || k).join("、")}
            </p>
          )}
        </div>

      </section>
    </div>
  );
}

// ── 子组件：维度滑块 ──

function DimSlider({
  label,
  emoji,
  value,
  onChange,
  labels,
}: {
  label: string;
  emoji: string;
  value: number;
  onChange: (v: number) => void;
  labels: [string, string, string];
}) {
  return (
    <div className="mt-4">
      <div className="flex justify-between items-center">
        <span className="text-xs font-semibold">
          {emoji} {label}
        </span>
        <span className="text-lg font-extrabold text-warm-accent">{value}</span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        step={0.5}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="mt-2 w-full h-1.5 rounded-full appearance-none cursor-pointer bg-warm-border"
        style={{
          background: `linear-gradient(to right, #c8a050 0%, #c8a050 ${((value - 1) / 4) * 100}%, #e0d8cc ${((value - 1) / 4) * 100}%)`,
        }}
      />
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>{labels[0]}</span>
        <span>{labels[1]}</span>
        <span>{labels[2]}</span>
      </div>
    </div>
  );
}
