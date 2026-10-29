import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AIChatPanel } from "@/components/ai-chat-panel";
import { getConversation, postChatMessage } from "@/lib/api";

vi.mock("next/navigation", () => ({
  usePathname: () => "/assessment/assessment-1",
}));
vi.mock("@/lib/api", () => ({
  getConversation: vi.fn(),
  clearConversation: vi.fn(),
  postChatMessage: vi.fn(),
}));

const scrollIntoView = vi.fn();
const scrollTo = vi.fn();
const nativeMethods = ["scrollIntoView", "scrollTo", "setPointerCapture", "releasePointerCapture"] as const;
const originalMethods = new Map(nativeMethods.map((name) => [
  name, Object.getOwnPropertyDescriptor(HTMLElement.prototype, name),
]));

function renderChat() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><AIChatPanel /></QueryClientProvider>);
  const messageList = view.container.querySelector<HTMLDivElement>(".overflow-y-auto")!;
  Object.defineProperty(messageList, "scrollHeight", { configurable: true, value: 320 });
  return { ...view, messageList, client };
}

function toggleChat() {
  const button = screen.getByRole("button", { name: "AI 商业顾问" });
  fireEvent.pointerDown(button, { pointerId: 1 });
  fireEvent.pointerUp(button, { pointerId: 1 });
}

describe("AI chat panel scrolling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("React", React);
    Object.defineProperties(HTMLElement.prototype, {
      scrollIntoView: { configurable: true, value: scrollIntoView },
      scrollTo: { configurable: true, value: scrollTo },
      setPointerCapture: { configurable: true, value: vi.fn() },
      releasePointerCapture: { configurable: true, value: vi.fn() },
    });
    vi.mocked(getConversation).mockResolvedValue({
      id: "conversation-1", assessment_id: "assessment-1", title: "企业咨询",
      messages: [], created_at: null,
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    for (const name of nativeMethods) {
      const original = originalMethods.get(name);
      if (original) Object.defineProperty(HTMLElement.prototype, name, original);
      else Reflect.deleteProperty(HTMLElement.prototype, name);
    }
  });

  it("does not scroll any element when mounted with the drawer closed", () => {
    const { messageList } = renderChat();
    expect(messageList.parentElement).toHaveClass("translate-x-full");
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it("scrolls only the message list when opened and while receiving streamed text", async () => {
    let streamController!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({ start(controller) { streamController = controller; } });
    vi.mocked(postChatMessage).mockResolvedValue(new Response(stream));
    const { messageList } = renderChat();
    scrollIntoView.mockClear();

    toggleChat();
    await waitFor(() => expect(scrollTo).toHaveBeenLastCalledWith({ top: 320, behavior: "smooth" }));
    expect(messageList.parentElement).toHaveClass("translate-x-0");
    expect(scrollTo.mock.instances.every((element) => element === messageList)).toBe(true);
    expect(scrollIntoView).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText("输入问题，或只上传资料让 AI 帮你总结..."), { target: { value: "分析企业" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "停止" })).toBeInTheDocument());
    scrollTo.mockClear();
    Object.defineProperty(messageList, "scrollHeight", { configurable: true, value: 640 });

    await act(async () => {
      streamController.enqueue(new TextEncoder().encode('data: {"token":"建议优先分析客户需求"}\n\n'));
    });
    expect(await screen.findByText("建议优先分析客户需求")).toBeInTheDocument();
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 640, behavior: "smooth" });
    expect(scrollTo.mock.instances.every((element) => element === messageList)).toBe(true);
    expect(scrollIntoView).not.toHaveBeenCalled();

    await act(async () => { streamController.close(); });
  });
});
