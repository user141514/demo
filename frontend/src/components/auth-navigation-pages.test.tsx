import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "@/app/login/page";
import RegisterPage from "@/app/register/page";

const mocks = vi.hoisted(() => ({
  authenticated: false, login: vi.fn(async () => {}), register: vi.fn(async () => {}), navigate: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("redirect=%2Flite%3Fid%3Dsaved") }));
vi.mock("next/image", () => ({ default: (props: React.ImgHTMLAttributes<HTMLImageElement>) => <img {...props} /> }));
vi.mock("@/providers/auth-provider", () => ({
  useAuth: () => ({ isAuthenticated: mocks.authenticated, isLoading: false, login: mocks.login, register: mocks.register }),
}));
vi.mock("@/lib/auth-navigation", async (original) => ({
  ...await original<typeof import("@/lib/auth-navigation")>(), navigateAfterAuth: mocks.navigate,
}));
beforeEach(() => { vi.stubGlobal("React", React); mocks.authenticated = false; vi.clearAllMocks(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("authentication page transitions", () => {
  it.each([["login", LoginPage], ["register", RegisterPage]] as const)("%s reloads the document with the protected destination after authentication", async (_, Page) => {
    const view = render(<Page />);
    mocks.authenticated = true;
    view.rerender(<Page />);
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith("/lite?id=saved"));
  });

  it("keeps the protected destination when going from login to registration", () => {
    render(<LoginPage />);
    expect(screen.getByRole("link", { name: "去注册" })).toHaveAttribute("href", "/register?redirect=%2Flite%3Fid%3Dsaved");
  });

  it("accepts a configured instructor account instead of a fixed username", async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /^讲师$/ }));
    fireEvent.change(screen.getByPlaceholderText("讲师账号或邮箱"), { target: { value: "faculty@example.com" } });
    fireEvent.change(screen.getByPlaceholderText("输入讲师密码"), { target: { value: "local-test-password" } });
    fireEvent.click(screen.getByRole("button", { name: "讲师登录" }));
    await waitFor(() => expect(mocks.login).toHaveBeenCalledWith("faculty@example.com", "local-test-password"));
  });
});
