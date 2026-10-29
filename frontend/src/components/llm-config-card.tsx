"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/hooks/use-toast";
import { apiBaseUrl } from "@/lib/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("auth_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 8) return "*".repeat(key.length);
  return key.slice(0, 4) + "****" + key.slice(-4);
}

interface LLMConfigSnapshot {
  mode: string;
  api_key: string;
  base_url: string;
  model: string;
  is_live: boolean;
}

export function LLMConfigCard() {
  const [config, setConfig] = useState<LLMConfigSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [formMode, setFormMode] = useState("mock");
  const [formKey, setFormKey] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("https://api.openai.com/v1");
  const [formModel, setFormModel] = useState("");

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBaseUrl}/api/admin/llm-config`, {
        headers: { "ngrok-skip-browser-warning": "true", ...authHeaders() },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setConfig(data);
      setFormMode(data.mode);
      setFormBaseUrl(data.base_url);
      setFormModel(data.model);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (!showForm) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [showForm]);

  const handleSave = () => {
    // Optimistic: close form + toast immediately
    const optimistic: LLMConfigSnapshot = {
      mode: formMode,
      api_key: formKey && !formKey.includes("*") ? maskKey(formKey) : (config?.api_key ?? ""),
      base_url: formBaseUrl,
      model: formModel,
      is_live: formMode === "live" && Boolean(formKey || config?.api_key) && Boolean(formModel),
    };
    setConfig(optimistic);
    setShowForm(false);
    setFormKey("");
    setSaving(true);

    const payload: Record<string, string> = { mode: formMode, base_url: formBaseUrl, model: formModel };
    if (formKey && !formKey.includes("*")) {
      payload.api_key = formKey;
    }

    fetch(`${apiBaseUrl}/api/admin/llm-config`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true", ...authHeaders() },
      body: JSON.stringify(payload),
    })
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const updated = await resp.json();
        setConfig(updated);
        toast({ title: "LLM 配置已保存", description: `模式: ${updated.mode}, 模型: ${updated.model || "未设置"}`, variant: "success" });
      })
      .catch((e) => {
        fetchConfig(); // rollback to server state
        toast({ title: "保存失败", description: e instanceof Error ? e.message : "请检查后端连接", variant: "destructive" });
      })
      .finally(() => setSaving(false));
  };

  if (loading) return (
    <div className="card space-y-3">
      <Skeleton className="h-6 w-32 rounded-xl" />
      <Skeleton className="h-4 w-48 rounded-xl" />
      <Skeleton className="h-4 w-40 rounded-xl" />
    </div>
  );

  if (error) return (
    <div className="card">
      <p className="text-sm text-muted-foreground">LLM 配置暂不可用</p>
      <Button variant="outline" size="sm" onClick={fetchConfig} className="mt-2">重试</Button>
    </div>
  );

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">LLM 配置</p>
          <h2 className="section-heading">大模型设置</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            运行时修改 LLM API Key、模型和 Base URL，无需重启服务。
          </p>
        </div>
        <Badge variant={config?.is_live ? "success" : "muted"}>
          {config?.is_live ? "真实" : config?.mode === "live" ? "配置不完整" : "模拟"}
        </Badge>
      </div>

      <div className="mt-4 grid gap-2 text-sm text-muted-foreground">
        <div className="flex justify-between gap-4">
          <span>API Key</span>
          <span className="font-mono text-xs">{config?.api_key || "未设置"}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>Base URL</span>
          <span className="font-mono text-xs truncate max-w-[280px]">{config?.base_url || "-"}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>Model</span>
          <span className="font-mono text-xs">{config?.model || "未设置"}</span>
        </div>
      </div>

      {!showForm ? (
        <Button variant="outline" size="sm" onClick={() => setShowForm(true)} className="mt-4">
          修改配置
        </Button>
      ) : (
        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">运行模式</span>
            <select
              value={formMode}
              onChange={(e) => setFormMode(e.target.value)}
              className="input-field"
            >
              <option value="mock">Mock（模拟数据）</option>
              <option value="live">Live（真实 API）</option>
            </select>
          </label>

          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">API Key</span>
            <Input
              type="password"
              value={formKey}
              onChange={(e) => setFormKey(e.target.value)}
              placeholder="sk-...（留空则保留现有 Key）"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">Base URL</span>
            <Input
              value={formBaseUrl}
              onChange={(e) => setFormBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm">
            <span className="font-medium">Model</span>
            <Input
              value={formModel}
              onChange={(e) => setFormModel(e.target.value)}
              placeholder="gpt-4o / deepseek-chat ..."
            />
          </label>

          <div className="flex gap-3">
            <Button variant="success" size="sm" onClick={handleSave} loading={saving}>
              保存配置
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>
              取消
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
