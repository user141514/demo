import React from "react";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LLMConfigCard } from "@/components/llm-config-card";

afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });
it("sends authentication when requesting instructor configuration", async () => {
  vi.stubGlobal("React", React);
  localStorage.setItem("auth_token", "qa-only-token");
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ mode: "mock", api_key: "", base_url: "", model: "", is_live: false }) }));
  vi.stubGlobal("fetch", fetchMock);
  render(<LLMConfigCard />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/admin/llm-config"), expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer qa-only-token" }) })));
});
