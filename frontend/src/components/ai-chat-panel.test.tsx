import React from "react";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { AIChatPanel } from "@/components/ai-chat-panel";

vi.mock("next/navigation", () => ({ usePathname: () => "/assessment/qa-assessment" }));
vi.mock("@/lib/api", () => ({
  getConversation: vi.fn(async () => ({ messages: [] })),
  clearConversation: vi.fn(), postChatMessage: vi.fn(),
}));

beforeEach(() => {
  vi.stubGlobal("React", React);
  HTMLElement.prototype.setPointerCapture = vi.fn();
  HTMLElement.prototype.releasePointerCapture = vi.fn();
  HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function togglePanel() {
  const trigger = screen.getByRole("button", { name: "AI 商业顾问" });
  fireEvent.pointerDown(trigger, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerUp(trigger, { pointerId: 1, clientX: 100, clientY: 100 });
}

describe("AI chat visibility", () => {
  it("keeps the closed drawer out of the page and never scrolls the document", () => {
    renderWithProviders(<AIChatPanel />);
    expect(screen.queryByText("AI 商业创新顾问")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("输入问题，或只上传资料让 AI 帮你总结...")).not.toBeInTheDocument();
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
  });

  it("opens and closes through its visible controls without scrolling ancestors", async () => {
    renderWithProviders(<AIChatPanel />);
    togglePanel();
    expect(screen.getByRole("dialog", { name: "AI 商业顾问" })).toBeVisible();
    await waitFor(() => expect(screen.getByText("AI 商业创新顾问")).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "关闭 AI 商业顾问" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
  });
});
