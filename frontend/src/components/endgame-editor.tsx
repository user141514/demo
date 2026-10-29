"use client";

import React, { useState } from "react";

import { Button } from "@/components/ui/button";
import type { UpdateEndgamePayload } from "@/lib/types";

type Props = {
  value: UpdateEndgamePayload;
  isSaving?: boolean;
  onSave: (payload: UpdateEndgamePayload) => Promise<void> | void;
  onCancel: () => void;
};

function listToText(value: string[]) {
  return value.join("\n");
}

function textToList(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function cloneValue(value: UpdateEndgamePayload): UpdateEndgamePayload {
  return {
    industry_essence: value.industry_essence,
    private_domain: {
      ...value.private_domain,
      key_strategies: [...value.private_domain.key_strategies],
    },
    ecosystem: {
      ...value.ecosystem,
      key_partners_to_engage: [...value.ecosystem.key_partners_to_engage],
    },
    opc: { ...value.opc },
    three_stage_strategy: {
      stage_1: {
        ...value.three_stage_strategy.stage_1,
        key_actions: [...value.three_stage_strategy.stage_1.key_actions],
        key_risks: [...value.three_stage_strategy.stage_1.key_risks],
      },
      stage_2: {
        ...value.three_stage_strategy.stage_2,
        key_actions: [...value.three_stage_strategy.stage_2.key_actions],
        key_risks: [...value.three_stage_strategy.stage_2.key_risks],
      },
      stage_3: {
        ...value.three_stage_strategy.stage_3,
        key_actions: [...value.three_stage_strategy.stage_3.key_actions],
        key_risks: [...value.three_stage_strategy.stage_3.key_risks],
      },
      key_risks: [...value.three_stage_strategy.key_risks],
    },
    strategic_paths: value.strategic_paths.map((path) => ({
      ...path,
      key_milestones: [...path.key_milestones],
      major_risks: [...path.major_risks],
    })),
    overall_narrative: value.overall_narrative,
  };
}

export function EndgameEditor({ value, isSaving, onSave, onCancel }: Props) {
  const [draft, setDraft] = useState(() => cloneValue(value));

  function updatePrivateDomain(
    patch: Partial<UpdateEndgamePayload["private_domain"]>,
  ) {
    setDraft((current) => ({
      ...current,
      private_domain: { ...current.private_domain, ...patch },
    }));
  }

  function updateEcosystem(
    patch: Partial<UpdateEndgamePayload["ecosystem"]>,
  ) {
    setDraft((current) => ({
      ...current,
      ecosystem: { ...current.ecosystem, ...patch },
    }));
  }

  function updateOpc(patch: Partial<UpdateEndgamePayload["opc"]>) {
    setDraft((current) => ({
      ...current,
      opc: { ...current.opc, ...patch },
    }));
  }

  function updateStage(
    key: "stage_1" | "stage_2" | "stage_3",
    patch: Partial<UpdateEndgamePayload["three_stage_strategy"]["stage_1"]>,
  ) {
    setDraft((current) => ({
      ...current,
      three_stage_strategy: {
        ...current.three_stage_strategy,
        [key]: {
          ...current.three_stage_strategy[key],
          ...patch,
        },
      },
    }));
  }

  function updateStageRisks(value: string) {
    setDraft((current) => ({
      ...current,
      three_stage_strategy: {
        ...current.three_stage_strategy,
        key_risks: textToList(value),
      },
    }));
  }

  function updatePath(
    index: number,
    patch: Partial<UpdateEndgamePayload["strategic_paths"][number]>,
  ) {
    setDraft((current) => ({
      ...current,
      strategic_paths: current.strategic_paths.map((path, currentIndex) =>
        currentIndex === index ? { ...path, ...patch } : path,
      ),
    }));
  }

  return (
    <section className="card">
      <div>
        <p className="section-label">手动修订</p>
        <h2 className="section-heading">核心竞争力推进策略</h2>
        <p className="mt-2 text-sm leading-7 text-warm-secondary">
          像商业画布诊断一样直接修改框内文字，保存后仍会写回原有结构化数据。
        </p>
      </div>

      <div className="mt-6 space-y-6">
        <div className="rounded-xl border border-warm-border-light bg-warm-surface p-5">
          <h3 className="font-heading text-base font-bold text-warm-text">
            三阶段推进策略
          </h3>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <StageEditor
              title="阶段 1"
              stage={draft.three_stage_strategy.stage_1}
              onChange={(patch) => updateStage("stage_1", patch)}
            />
            <StageEditor
              title="阶段 2"
              stage={draft.three_stage_strategy.stage_2}
              onChange={(patch) => updateStage("stage_2", patch)}
            />
            <StageEditor
              title="阶段 3"
              stage={draft.three_stage_strategy.stage_3}
              onChange={(patch) => updateStage("stage_3", patch)}
            />
          </div>
          <div className="mt-4">
            <TextAreaField
              label="整体关键风险"
              value={listToText(draft.three_stage_strategy.key_risks)}
              onChange={updateStageRisks}
              helper="每行一个风险。"
            />
          </div>
        </div>

        {draft.strategic_paths.length > 0 ? (
          <div className="grid gap-4 lg:grid-cols-3">
            {draft.strategic_paths.map((path, index) => (
              <SectionCard key={`path-${index}`} title={`策略路径 ${index + 1}`}>
                <TextAreaField
                  label="路径名称"
                  value={path.path_name}
                  minHeight="min-h-[48px]"
                  onChange={(nextValue) =>
                    updatePath(index, { path_name: nextValue })
                  }
                />
                <SelectField
                  label="路径类型"
                  value={path.path_type}
                  options={["保守", "均衡", "激进"]}
                  onChange={(nextValue) =>
                    updatePath(index, {
                      path_type: nextValue as "保守" | "均衡" | "激进",
                    })
                  }
                />
                <TextAreaField
                  label="推进节奏"
                  value={path.execution_rhythm}
                  onChange={(nextValue) =>
                    updatePath(index, { execution_rhythm: nextValue })
                  }
                />
                <TextAreaField
                  label="关键里程碑"
                  value={listToText(path.key_milestones)}
                  onChange={(nextValue) =>
                    updatePath(index, { key_milestones: textToList(nextValue) })
                  }
                  helper="每行一个里程碑。"
                />
                <TextAreaField
                  label="能力前提"
                  value={path.capability_requirements}
                  onChange={(nextValue) =>
                    updatePath(index, { capability_requirements: nextValue })
                  }
                />
                <TextAreaField
                  label="预期成果"
                  value={path.expected_outcomes}
                  onChange={(nextValue) =>
                    updatePath(index, { expected_outcomes: nextValue })
                  }
                />
                <TextAreaField
                  label="主要风险"
                  value={listToText(path.major_risks)}
                  onChange={(nextValue) =>
                    updatePath(index, { major_risks: textToList(nextValue) })
                  }
                  helper="每行一个风险。"
                />
                <SelectField
                  label="推荐等级"
                  value={path.recommendation_level}
                  options={["推荐", "可选", "不推荐"]}
                  onChange={(nextValue) =>
                    updatePath(index, {
                      recommendation_level: nextValue as
                        | "推荐"
                        | "可选"
                        | "不推荐",
                    })
                  }
                />
              </SectionCard>
            ))}
          </div>
        ) : null}

        <div className="rounded-xl border border-warm-warning/20 bg-warm-warning/5 p-4 text-sm leading-7 text-warm-secondary">
          保存后，下游结论会按依赖链自动失效，需要重新生成。
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={() => onSave(draft)} loading={isSaving} disabled={isSaving}>
            {isSaving ? "保存中..." : "保存修改并清除下游"}
          </Button>
          <Button variant="outline" onClick={onCancel} disabled={isSaving}>
            取消
          </Button>
        </div>
      </div>
    </section>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-surface p-5">
      <h3 className="font-heading text-base font-bold text-warm-text">{title}</h3>
      <div className="mt-4 space-y-3">{children}</div>
    </div>
  );
}

function StageEditor({
  title,
  stage,
  onChange,
}: {
  title: string;
  stage: UpdateEndgamePayload["three_stage_strategy"]["stage_1"];
  onChange: (
    patch: Partial<UpdateEndgamePayload["three_stage_strategy"]["stage_1"]>,
  ) => void;
}) {
  return (
    <div className="rounded-xl border border-warm-border-light bg-warm-inset p-4">
      <h4 className="text-sm font-semibold text-warm-accent">{title}</h4>
      <div className="mt-3 space-y-3">
        <TextAreaField
          label="标题"
          value={stage.title}
          minHeight="min-h-[44px]"
          onChange={(nextValue) => onChange({ title: nextValue })}
        />
        <TextAreaField
          label="重点"
          value={stage.focus}
          minHeight="min-h-[44px]"
          onChange={(nextValue) => onChange({ focus: nextValue })}
        />
        <TextAreaField
          label="策略"
          value={stage.strategy}
          onChange={(nextValue) => onChange({ strategy: nextValue })}
        />
        <TextAreaField
          label="目标"
          value={stage.objective}
          onChange={(nextValue) => onChange({ objective: nextValue })}
        />
        <TextAreaField
          label="关键动作"
          value={listToText(stage.key_actions)}
          onChange={(nextValue) => onChange({ key_actions: textToList(nextValue) })}
          helper="每行一个动作。"
        />
        <TextAreaField
          label="关键风险"
          value={listToText(stage.key_risks)}
          onChange={(nextValue) => onChange({ key_risks: textToList(nextValue) })}
          helper="每行一个风险。"
        />
      </div>
    </div>
  );
}

function TextAreaField({
  label,
  value,
  onChange,
  helper,
  minHeight = "min-h-[70px]",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  helper?: string;
  minHeight?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="flex flex-col gap-1">
        <span className="text-[10px] uppercase text-warm-muted">{label}</span>
        <textarea
          className={`w-full resize-y rounded border border-warm-border bg-warm-surface p-2 text-xs leading-5 text-warm-text ${minHeight}`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      {helper ? <span className="text-[10px] text-warm-muted">{helper}</span> : null}
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase text-warm-muted">{label}</span>
      <select
        className="w-full rounded border border-warm-border bg-warm-surface p-2 text-xs leading-5 text-warm-text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
