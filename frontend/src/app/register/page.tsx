"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { useAuth } from "@/providers/auth-provider";
import { getAuthRedirect, navigateAfterAuth } from "@/lib/auth-navigation";

function RegisterPageContent() {
  const { register, isAuthenticated, isLoading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const redirect = getAuthRedirect(searchParams.get("redirect"));

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      navigateAfterAuth(redirect);
    }
  }, [authLoading, isAuthenticated, redirect]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (
      !email.trim() ||
      !displayName.trim() ||
      !companyName.trim() ||
      !jobTitle.trim() ||
      !password
    ) {
      return;
    }

    setSubmitting(true);
    try {
      await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        company_name: companyName.trim(),
        job_title: jobTitle.trim(),
      });
    } catch (error) {
      toast({
        title: "注册失败",
        description:
          error instanceof Error ? error.message : "请稍后重试。",
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
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-xl">
        <div className="page-header text-center mb-6">
          <h1 className="font-heading text-2xl font-bold text-warm-text">注册</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            创建账号并进入主流程工作台
          </p>
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
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
              <span className="font-medium">姓名 / 昵称</span>
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="请输入姓名或昵称"
                required
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium">公司名称</span>
              <Input
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="请输入公司名称"
                required
              />
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium">角色 / 职位</span>
              <Input
                value={jobTitle}
                onChange={(event) => setJobTitle(event.target.value)}
                placeholder="如：业务负责人 / 运营总监"
                required
              />
            </label>
          </div>

          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">登录密码</span>
            <Input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="至少 6 位"
              required
              minLength={6}
            />
          </label>

          <Button type="submit" loading={submitting} className="w-full">
            {submitting ? "注册中..." : "注册并进入系统"}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            已有账号？{" "}
            <Link href={`/login?redirect=${encodeURIComponent(redirect)}`} className="text-primary hover:underline">
              去登录
            </Link>
          </p>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          如果忘记密码，可在登录页通过邮箱重置。
        </p>

        <p className="mt-4 text-center">
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

export default function RegisterPage() {
  return <Suspense fallback={<p>注册页加载中...</p>}><RegisterPageContent /></Suspense>;
}
