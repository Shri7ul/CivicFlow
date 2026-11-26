import Link from "next/link";

import { LandingFooter } from "@/components/landing/landing-footer";
import { LandingHeader } from "@/components/landing/landing-header";
import { LandingIcon } from "@/components/landing/landing-icons";
import {
  ArchitectureSection,
  CapabilitiesSection,
  FinalCtaSection,
  PilotStatusSection,
  TrustSection,
  WorkflowSection,
} from "@/components/landing/landing-sections";
import { hero } from "@/components/landing/landing-content";
import { HeroProductPreview } from "@/components/landing/product-preview";

export default function HomePage() {
  return (
    <div id="top" className="relative min-h-dvh overflow-hidden">
      <div aria-hidden="true" className="site-grid" />
      <div aria-hidden="true" className="site-glow" />

      <LandingHeader />

      <main>
        <section className="mx-auto grid w-full max-w-7xl gap-12 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)] lg:items-center lg:gap-12 lg:px-10 lg:pb-20 lg:pt-20">
          <div className="min-w-0">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/5 px-3 py-1.5 text-xs font-medium text-accent">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" />
              {hero.eyebrow}
            </span>

            <h1 className="mt-6 max-w-2xl text-balance text-[2.4rem] font-semibold leading-[1.08] tracking-[-0.035em] text-foreground sm:text-5xl lg:text-[3.3rem] xl:text-[3.8rem]">
              {hero.headlineLead}
              <br />
              <span className="bg-gradient-to-r from-accent via-emerald-300 to-accent-cyan bg-clip-text text-transparent">
                {hero.headlineAccent}
              </span>
            </h1>

            <p className="mt-6 max-w-xl text-pretty text-base leading-7 text-muted sm:text-lg sm:leading-8">
              {hero.description}
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href={hero.primary.href}
                className="group inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-background transition hover:bg-accent/90"
              >
                {hero.primary.label}
                <LandingIcon
                  name="arrow"
                  className="size-4 transition-transform group-hover:translate-x-0.5"
                />
              </Link>
              <Link
                href={hero.secondary.href}
                className="inline-flex items-center justify-center rounded-lg border border-line bg-surface px-5 py-3 text-sm font-medium text-foreground transition hover:bg-surface-raised"
              >
                {hero.secondary.label}
              </Link>
            </div>

            <ul className="mt-9 flex flex-wrap gap-x-5 gap-y-2 border-t border-line pt-5 text-xs text-muted">
              {hero.assurances.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="size-1 rounded-full bg-accent/70"
                  />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="min-w-0 lg:pl-2">
            <HeroProductPreview />
          </div>
        </section>

        <CapabilitiesSection />
        <WorkflowSection />
        <ArchitectureSection />
        <TrustSection />
        <PilotStatusSection />
        <FinalCtaSection />
      </main>

      <LandingFooter />
    </div>
  );
}
