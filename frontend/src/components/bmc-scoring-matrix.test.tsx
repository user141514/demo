import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BmcScoringMatrix } from "@/components/bmc-scoring-matrix";
import { BMC_MODULES } from "@/lib/types";
import type { BmcScoringResult } from "@/lib/types";

const saveMock = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/use-bmc-scoring", () => ({
  useSaveBMCScoring: () => ({ isPending: false, mutateAsync: saveMock }),
  useAutoDeriveBMCScoring: () => ({ isPending: false, mutateAsync: vi.fn() }),
  useCalculateBMCScoring: () => ({ isPending: false, mutateAsync: vi.fn() }),
}));
vi.mock("@/hooks/use-toast", () => ({ toast: vi.fn() }));

function scoring(): BmcScoringResult {
  const values: Record<string, number[]> = {
    key_resources: [3.5, 5, 3],
    value_propositions: [3.5, 3.5, 3],
    customer_segments: [3, 3.5, 3],
    key_partnerships: [2.5, 4, 3],
  };
  return {
    assessment_id: "a1",
    module_results: BMC_MODULES.map((item) => {
      const [pain, data, feasibility] = values[item.key] ?? [3, 3, 3];
      return { ...item, pain, data, feasibility, raw_score: 0, normalized_score: 0,
        zone: "hold", veto_status: "none", veto_reason: null,
        recommendation_level: "none", recommendation_label: "", recommendation_stars: "" };
    }),
    top_3_keys: ["key_resources", "value_propositions", "customer_segments"],
    top_3_results: [], complementarity_warning: null,
  };
}

function renderMatrix(selected: string[] = []) {
  return render(<BmcScoringMatrix assessmentId="a1" existingScoring={scoring()}
    savedSelectedKeys={selected} canvasDiagnosis={null} />);
}

function recommendationPanel() {
  return screen.getByText("🎯 Top 3 突破要素推荐").closest(".card") as HTMLElement;
}

describe("BmcScoringMatrix feedback contract", () => {
  beforeEach(() => {
    saveMock.mockReset().mockResolvedValue({});
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  });

  it("matches score-preview ranking and saves exactly one selected module", async () => {
    renderMatrix();
    const panel = recommendationPanel();
    const text = panel.textContent!;
    expect(text.indexOf("核心资源")).toBeLessThan(text.indexOf("价值主张"));
    expect(text.indexOf("价值主张")).toBeLessThan(text.indexOf("客户细分"));
    const save = within(panel).getByRole("button", { name: /保存并锁定突破要素/ });
    expect(save).toBeDisabled();
    fireEvent.click(within(panel).getByText("核心资源"));
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(saveMock).toHaveBeenCalledWith({
      assessmentId: "a1", payload: expect.objectContaining({ selected_keys: ["key_resources"] }),
    }));
  });

  it("restores an outside-Top3 saved choice and lets the user change it", async () => {
    renderMatrix(["cost_structure"]);
    fireEvent.click(screen.getByRole("button", { name: /重新调整突破要素/ }));
    const cost = screen.getByRole("button", { name: /C\$ 成本结构/ });
    expect(cost).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(cost);
    fireEvent.click(screen.getByRole("button", { name: /KA 关键业务/ }));
    fireEvent.click(screen.getByRole("button", { name: /保存并锁定突破要素/ }));
    await waitFor(() => expect(saveMock).toHaveBeenCalledWith({
      assessmentId: "a1", payload: expect.objectContaining({ selected_keys: ["key_activities"] }),
    }));
  });
});
