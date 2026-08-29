import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/common/ThemeToggle";

const HERO_IMAGE = "/codethera-hero.png";

interface AuthLayoutProps {
  children: ReactNode;
}

function AuthGradientBackground() {
  return (
    <>
      <div className="absolute inset-0 bg-slate-950" />
      <div className="absolute inset-0 bg-gradient-to-br from-blue-950/80 via-slate-950 to-emerald-950/40" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(59,130,246,0.15),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_80%,rgba(16,185,129,0.1),transparent_50%)]" />
    </>
  );
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen">
      <AuthGradientBackground />

      <div className="absolute right-4 top-4 z-20">
        <ThemeToggle className="rounded-lg bg-white/10 text-white hover:bg-white/20" />
      </div>

      <aside className="relative z-10 hidden w-1/2 flex-col items-center justify-center p-10 lg:flex">
        <img
          src={HERO_IMAGE}
          alt="CodeThera — Diagnose, Heal, Improve"
          className="max-h-[min(70vh,480px)] w-full max-w-2xl object-contain drop-shadow-2xl"
        />
      </aside>

      <main className="relative z-10 flex w-full flex-col items-center justify-center px-6 py-12 lg:w-1/2">
        <div className="w-full max-w-md">
          <div className="mb-8 flex justify-center lg:hidden">
            <img src={HERO_IMAGE} alt="CodeThera" className="h-28 w-auto max-w-full object-contain" />
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
