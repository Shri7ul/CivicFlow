import { siteConfig } from "@/config/app";

export function SiteFooter() {
  return (
    <footer className="border-t border-white/5">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-5 py-8 text-xs text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <p>
          {siteConfig.name} v{siteConfig.version} · {siteConfig.phase}
        </p>
        <p>Built with Next.js, MapLibre, FastAPI, and Supabase.</p>
      </div>
    </footer>
  );
}
