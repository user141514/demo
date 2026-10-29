"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useAuth } from "@/providers/auth-provider";

type Role = "student" | "teacher";

function LoginPageContent() {
  const { login, isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") ?? "/";

  const [role, setRole] = useState<Role>("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace(redirect);
    }
  }, [authLoading, isAuthenticated, redirect, router]);

  const loginEmail = useMemo(() => {
    if (role === "teacher") {
      return "teacher";
    }
    return email.trim();
  }, [email, role]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!password) return;
    if (role === "student" && !loginEmail) return;

    setSubmitting(true);
    try {
      await login(loginEmail, password);
    } catch (error) {
      toast({
        title: "登录失败",
        description:
          error instanceof Error ? error.message : "请检查账号和密码后重试。",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading || isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-warm-accent border-t-transparent" />
          <p className="text-sm text-muted-foreground">正在验证登录状态...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="page-header text-center mb-6">
          <h1 className="font-heading text-2xl font-bold text-warm-text">
            登录
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            美太 AI 商业创新智能体
          </p>
        </div>

        <div className="mb-6 flex gap-1 rounded-lg bg-muted p-1">
          <button
            type="button"
            onClick={() => {
              setRole("student");
              setEmail("");
              setPassword("");
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              role === "student"
                ? "bg-background text-warm-text shadow-sm"
                : "text-muted-foreground hover:text-warm-text"
            }`}
          >
            学员
          </button>
          <button
            type="button"
            onClick={() => {
              setRole("teacher");
              setPassword("");
            }}
            className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
              role === "teacher"
                ? "bg-background text-warm-text shadow-sm"
                : "text-muted-foreground hover:text-warm-text"
            }`}
          >
            管理员
          </button>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
          {role === "student" ? (
            <>
              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium">邮箱</span>
                <Input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="your@email.com"
                  required
                  autoFocus
                />
              </label>

              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium">密码</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="输入密码"
                  required
                  minLength={6}
                />
              </label>

              <Button type="submit" loading={submitting} className="w-full">
                {submitting ? "登录中..." : "登录"}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                忘记密码？
                {" "}
                <Link href="/forgot-password" className="text-primary hover:underline">
                  邮箱找回
                </Link>
                {" "}
                还没有账号？
                {" "}
                <Link href="/register" className="text-primary hover:underline">
                  去注册
                </Link>
              </p>
            </>
          ) : (
            <>
              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium">账号</span>
                <Input
                  value="teacher"
                  disabled
                  className="cursor-not-allowed bg-muted text-muted-foreground"
                />
              </label>

              <label className="flex flex-col gap-2 text-sm">
                <span className="font-medium">密码</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="输入管理员密码"
                  required
                  autoFocus
                />
              </label>

              <Button type="submit" loading={submitting} className="w-full">
                {submitting ? "登录中..." : "管理员登录"}
              </Button>
            </>
          )}
        </form>

        <section className="mt-6 rounded-2xl border border-warm-border bg-warm-surface p-4">
          <p className="text-center text-sm font-medium text-warm-text">
            需要帮助？
          </p>
          <p className="mt-2 text-center text-xs leading-6 text-muted-foreground">
            登录问题优先使用邮箱找回密码；使用问题可联系下方咨询入口。
          </p>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="text-center">
              <Image
                src="/qrcodes/meitai-consulting-official-account.jpg"
                alt="美太咨询公众号"
                width={144}
                height={144}
                className="mx-auto rounded-lg"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                美太咨询公众号
              </p>
            </div>
            <div className="text-center">
              <Image
                src="/qrcodes/meitai-usage-consulting.jpg"
                alt="使用咨询"
                width={144}
                height={144}
                className="mx-auto rounded-lg"
              />
              <p className="mt-2 text-xs text-muted-foreground">使用咨询</p>
            </div>
          </div>
        </section>

        <p className="mt-6 text-center">
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-warm-text"
          >
            返回首页
          </Link>
        </p>
      </div>
    </div>
  );
}

function LoginPageFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-4 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-warm-accent border-t-transparent" />
        <p className="text-sm text-muted-foreground">登录页加载中...</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageFallback />}>
      <LoginPageContent />
    </Suspense>
  );
}
