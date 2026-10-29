import { describe, expect, it } from "vitest";
import { getAuthRedirect } from "@/lib/auth-navigation";

describe("authentication destinations", () => {
  it("preserves protected paths and company/result query parameters", () => {
    expect(getAuthRedirect("/lite?id=saved-result")).toBe("/lite?id=saved-result");
    expect(getAuthRedirect("/assessment?company_name=Demo%20Company")).toBe("/assessment?company_name=Demo%20Company");
  });
  it.each([null, "https://example.com", "//example.com", "/\\example.com", "/login?redirect=/login", "/register", "/\nexample.com"])("rejects unsafe or looping destination %s", (value) => {
    expect(getAuthRedirect(value)).toBe("/");
  });
});
