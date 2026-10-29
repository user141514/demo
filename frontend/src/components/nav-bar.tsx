"use client";

import { useState } from "react";
import Link from "next/link";

import { useAuth } from "@/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function NavBar() {
  const { isAuthenticated, user, isInstructor, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <Link
            href="/"
            className="font-heading text-lg font-bold text-warm-text transition-colors hover:text-primary"
          >
            美太 AI
          </Link>
          <div className="hidden items-center gap-4 md:flex">
            <Link
              href="/"
              className="text-sm text-muted-foreground transition-colors hover:text-warm-text"
            >
              首页
            </Link>
            {isAuthenticated ? (
              <>
                <Link
                  href="/assessment"
                  className="text-sm text-muted-foreground transition-colors hover:text-warm-text"
                >
                  主流程工作台
                </Link>
                <Link
                  href="/history"
                  className="text-sm text-muted-foreground transition-colors hover:text-warm-text"
                >
                  评估历史
                </Link>
              </>
            ) : null}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <div className="hidden items-center gap-3 md:flex">
              <span className="text-sm text-warm-text">
                {user?.display_name || user?.email}
              </span>
              {isInstructor ? <Badge variant="accent">管理员</Badge> : null}
              <Button variant="ghost" size="sm" onClick={logout}>
                退出
              </Button>
            </div>
          ) : (
            <Link href="/login">
              <Button variant="outline" size="sm">
                登录
              </Button>
            </Link>
          )}

          <button
            type="button"
            className="p-2 text-muted-foreground hover:text-warm-text md:hidden"
            onClick={() => setMenuOpen((current) => !current)}
            aria-label="菜单"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              {menuOpen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {menuOpen ? (
        <div className="space-y-2 border-t border-border bg-background px-6 py-3 md:hidden">
          <Link
            href="/"
            className="block py-2 text-sm text-muted-foreground hover:text-warm-text"
            onClick={() => setMenuOpen(false)}
          >
            首页
          </Link>
          {isAuthenticated ? (
            <>
              <Link
                href="/assessment"
                className="block py-2 text-sm text-muted-foreground hover:text-warm-text"
                onClick={() => setMenuOpen(false)}
              >
                主流程工作台
              </Link>
              <Link
                href="/history"
                className="block py-2 text-sm text-muted-foreground hover:text-warm-text"
                onClick={() => setMenuOpen(false)}
              >
                评估历史
              </Link>
              <div className="flex items-center justify-between border-t border-border pt-2">
                <span className="text-sm">{user?.display_name || user?.email}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    logout();
                    setMenuOpen(false);
                  }}
                >
                  退出
                </Button>
              </div>
            </>
          ) : (
            <Link
              href="/login"
              className="block py-2 text-sm font-medium text-primary"
              onClick={() => setMenuOpen(false)}
            >
              登录
            </Link>
          )}
        </div>
      ) : null}
    </nav>
  );
}
