import Link from "next/link";
import styles from "@/components/lite-theme.module.css";

export default function StartPage() {
  return (
    <main className={`${styles.theme} min-h-screen px-6 py-10`}>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
        <section className="page-header space-y-4">
          <Link href="/" className="btn-secondary text-xs">返回首页</Link>
          <span className="badge badge-accent">AI 商业创新智能体</span>
          <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text">选择适合你的探索方式</h1>
          <p className="max-w-3xl text-base leading-7 text-warm-secondary">快速了解企业的 AI 创新机会，或通过完整问卷深入构建商业创新方案。</p>
        </section>
        <section aria-label="版本选择" className="grid gap-6 md:grid-cols-2">
          <article className="flex flex-col rounded-2xl border border-warm-accent bg-white p-8">
            <span className="text-sm font-medium text-warm-accent">快速开始 · Lite</span>
            <h2 className="mt-3 font-heading text-3xl font-bold text-warm-text">精简版</h2>
            <p className="mt-4 text-sm leading-7 text-warm-secondary">仅填写公司工商全称，可选上传资料。先确认联网生成的企业画像，再获得初步 AI 创新建议。</p>
            <ul className="my-6 list-disc space-y-3 pl-5 text-sm text-warm-secondary">
              <li>公开信息与来源可追溯</li>
              <li>企业现状、2–3 个创新方向、下一步行动与风险</li>
              <li>资料不足时可补充资料或升级完整版</li>
            </ul>
            <Link href="/lite" className="btn-primary mt-auto self-start">进入精简版</Link>
          </article>
          <article className="flex flex-col rounded-2xl border border-warm-border bg-white p-8">
            <span className="text-sm font-medium text-warm-muted">深度分析 · Full</span>
            <h2 className="mt-3 font-heading text-3xl font-bold text-warm-text">完整版</h2>
            <p className="mt-4 text-sm leading-7 text-warm-secondary">导入前置材料或填写企业问卷，沿用完整咨询流程，逐步形成可实施的商业创新方案。</p>
            <ul className="my-6 list-disc space-y-3 pl-5 text-sm text-warm-secondary">
              <li>企业画像、九格商业画布与突破要素</li>
              <li>创新方向、竞争力、商业终局、场景与案例</li>
              <li>14 章节报告、导出、跟进与管理员功能</li>
            </ul>
            <Link href="/assessment" className="btn-secondary mt-auto self-start">进入完整版</Link>
          </article>
        </section>
      </div>
    </main>
  );
}
