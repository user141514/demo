"use client";

import { useEffect, useState } from "react";
import type { InstructorDashboardResponse, StudentSummary } from "@/lib/types";
import { getInstructorDashboard, batchComment, instructorExportCsv, createInstructor } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";

const progressIcon = (flag: boolean, label: string) => (
  flag ? <span role="img" aria-label={`${label}：已完成`}>✅</span> : <span role="img" aria-label={`${label}：未开始`}>⬜</span>
);

export function InstructorDashboard() {
  const [data, setData] = useState<InstructorDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [commentDraft, setCommentDraft] = useState("");
  const [commentStatus, setCommentStatus] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [groupFilter, setGroupFilter] = useState<string>("全部");

  function resetCreateForm() {
    setNewEmail("");
    setNewPassword("");
    setNewName("");
    setCreateError(null);
  }

  useEffect(() => { loadDashboard(); }, []);

  async function loadDashboard() {
    setLoading(true);
    try { const result = await getInstructorDashboard(); setData(result); }
    catch (e) { setError(e instanceof Error ? e.message : "加载管理员仪表盘失败"); }
    finally { setLoading(false); }
  }

  async function handleBatchComment() {
    if (!commentDraft.trim() || selectedIds.size === 0) return;
    try {
      const result = await batchComment({ assessment_ids: Array.from(selectedIds), comment: commentDraft });
      setCommentStatus(`已点评 ${result.updated_count} 名学员。`);
      setCommentDraft(""); loadDashboard();
    } catch { setCommentStatus("点评提交失败，请重试。"); }
  }

  async function handleExport() {
    try {
      const result = await instructorExportCsv();
      const blob = new Blob([result.content], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `instructor_export_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch { setError("导出失败"); }
  }

  async function handleCreateInstructor(e: React.FormEvent) {
    e.preventDefault();
    if (!newEmail.trim() || !newPassword) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createInstructor({
        email: newEmail.trim(),
        password: newPassword,
        display_name: newName.trim() || undefined,
      });
      resetCreateForm();
      setShowCreateDialog(false);
      toast({ title: "创建成功", description: `管理员 ${newEmail} 已创建。` });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  function toggleSelect(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  }

  function toggleSelectAll(students: StudentSummary[]) {
    if (selectedIds.size === students.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(students.map((s) => s.assessment_id)));
  }

  if (loading) return <div className="card text-sm text-warm-secondary">正在加载管理员仪表盘...</div>;
  if (error || !data) return <div className="card text-sm text-warm-danger">{error || "暂无数据"}</div>;

  const filtered = groupFilter === "全部" ? data.students : data.students.filter((s) => (s.class_group || "未分组") === groupFilter);

  return (
    <div className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">管理员工作台</p>
          <h2 className="section-heading">管理员工作台</h2>
        </div>
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => setShowCreateDialog(true)}
            className="btn-primary text-xs">创建管理员</button>
          <button type="button" onClick={handleExport} className="btn-secondary text-xs">导出 CSV</button>
        </div>
      </div>

      {data.groups.length > 1 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {["全部", ...data.groups].map((g) => (
            <button key={g} type="button" onClick={() => setGroupFilter(g)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                groupFilter === g ? "bg-warm-accent text-white shadow-sm" : "badge badge-muted"
              }`}
            >
              {g}
              {g !== "全部" && data.summary_by_group[g] != null && <span className="ml-1 opacity-60">({data.summary_by_group[g]})</span>}
            </button>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-warm-border-light bg-warm-inset p-3">
        <input className="input-field flex-1 min-w-[240px]" placeholder={`批量点评（已选 ${selectedIds.size} 人）...`}
          value={commentDraft} onChange={(e) => setCommentDraft(e.target.value)} />
        <button type="button" onClick={handleBatchComment} disabled={selectedIds.size === 0 || !commentDraft.trim()}
          className="btn-primary text-sm flex-shrink-0">提交点评</button>
        {commentStatus && <span className="text-xs text-warm-success">{commentStatus}</span>}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-warm-border-light">
              <th className="pb-2 pr-2"><input type="checkbox" aria-label="全选当前分组学员" checked={selectedIds.size === filtered.length && filtered.length > 0}
                onChange={() => toggleSelectAll(filtered)} className="rounded" /></th>
              <th className="pb-2 pr-3 font-medium text-warm-muted">企业</th>
              <th className="pb-2 px-2 font-medium text-warm-muted hidden sm:table-cell">行业</th>
              <th className="pb-2 px-2 font-medium text-warm-muted hidden md:table-cell">分组</th>
              <th className="pb-2 px-1 text-center font-medium text-warm-muted"><abbr title="企业画像 (Profile)">P</abbr></th>
              <th className="pb-2 px-1 text-center font-medium text-warm-muted"><abbr title="商业画布 (Canvas)">C</abbr></th>
              <th className="pb-2 px-1 text-center font-medium text-warm-muted"><abbr title="突破要素 (Breakthrough)">B</abbr></th>
              <th className="pb-2 px-1 text-center font-medium text-warm-muted"><abbr title="场景推荐 (Scenario)">S</abbr></th>
              <th className="pb-2 px-1 text-center font-medium text-warm-muted"><abbr title="报告 (Report)">R</abbr></th>
              <th className="pb-2 px-2 font-medium text-warm-muted hidden lg:table-cell">管理员备注</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((student) => (
              <tr key={student.assessment_id} className="border-b border-warm-border-light hover:bg-warm-inset">
                <td className="py-2 pr-2"><input type="checkbox" aria-label={`选择 ${student.company_name}`} checked={selectedIds.has(student.assessment_id)}
                  onChange={() => toggleSelect(student.assessment_id)} className="rounded" /></td>
                <td className="py-2 pr-3"><p className="font-medium text-warm-text truncate max-w-[140px]">{student.company_name}</p></td>
                <td className="py-2 px-2 hidden sm:table-cell"><span className="text-warm-muted">{student.industry}</span></td>
                <td className="py-2 px-2 hidden md:table-cell"><span className="badge badge-muted text-[10px]">{student.class_group || "未分组"}</span></td>
                <td className="py-2 px-1 text-center text-[10px]">{progressIcon(student.has_profile, "企业画像")}</td>
                <td className="py-2 px-1 text-center text-[10px]">{progressIcon(student.has_canvas, "商业画布")}</td>
                <td className="py-2 px-1 text-center text-[10px]">{progressIcon(student.has_breakthrough, "突破要素")}</td>
                <td className="py-2 px-1 text-center text-[10px]">{progressIcon(student.has_scenarios, "场景推荐")}</td>
                <td className="py-2 px-1 text-center text-[10px]">{student.has_report ? <span role="img" aria-label="已有报告">📄</span> : <span role="img" aria-label="无报告">⬜</span>}</td>
                <td className="py-2 px-2 hidden lg:table-cell"><p className="text-[10px] text-warm-muted max-w-[180px] truncate">{student.instructor_comment || "—"}</p></td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={10} className="py-6 text-center text-warm-muted">暂无所选分组的学员数据</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={showCreateDialog} onOpenChange={(open) => {
        if (!open) { resetCreateForm(); }
        setShowCreateDialog(open);
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>创建管理员账号</DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreateInstructor} className="space-y-4">
            {createError && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{createError}</div>
            )}

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">邮箱</span>
              <Input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="instructor@example.com"
                required
                autoFocus
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">显示名称（选填）</span>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="张老师"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">密码（至少 6 位）</span>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="输入密码"
                required
                minLength={6}
              />
            </label>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button type="button" variant="outline"
                onClick={() => { resetCreateForm(); setShowCreateDialog(false); }}>
                取消
              </Button>
              <Button type="submit" loading={creating}>
                {creating ? "创建中..." : "创建管理员"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
