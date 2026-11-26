import Link from "next/link";
import { Fragment, type ReactNode } from "react";

import { BackendStatus } from "@/components/status/backend-status";
import {
  architectureLayers,
  capabilities,
  finalCta,
  governanceTiers,
  statusRows,
  workflowSteps,
  type GovernanceTier,
  type StatusRow,
} from "@/components/landing/landing-content";
import { LandingIcon } from "@/components/landing/landing-icons";
import { PlatformPreview } from "@/components/landing/product-preview";

const toneStyles = {
  implemented: {
    border: "border-accent/20",
    surface: "bg-accent/[0.035]",
    dot: "bg-accent",
    text: "text-accent",
  },
  research: {
    border: "border-accent-cyan/20",
    surface: "bg-accent-cyan/[0.035]",
    dot: "bg-accent-cyan",
    text: "text-accent-cyan",
  },
  external: {
    border: "border-line",
    surface: "bg-surface",
    dot: "bg-muted",
    text: "text-muted",
  },
  inactive: {
    border: "border-line",
    surface: "bg-surface",
    dot: "bg-muted",
    text: "text-muted",
  },
} as const;

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-accent/80">
      {children}
    </p>
  );
}

function TierCard({ tier }: { tier: GovernanceTier }) {
  const tone = toneStyles[tier.tone];
  return (
    <article
      className={`rounded-xl border p-5 sm:p-6 ${tone.border} ${tone.surface}`}
    >
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className={`size-2 rounded-full ${tone.dot}`}
        />
        <h3 className={`text-sm font-semibold ${tone.text}`}>{tier.label}</h3>
      </div>
      <p className="mt-3 text-sm leading-6 text-foreground/80">{tier.summary}</p>
      <ul className="mt-5 space-y-3 border-t border-line/80 pt-4">
        {tier.items.map((item) => (
          <li key={item} className="flex gap-2.5 text-sm leading-5 text-muted">
            <span
              aria-hidden="true"
              className={`mt-2 size-1 shrink-0 rounded-full ${tone.dot}`}
            />
            {item}
          </li>
        ))}
      </ul>
    </article>
  );
}

function StatusItem({ row }: { row: StatusRow }) {
  const tone = toneStyles[row.tone];
  return (
    <div className="flex flex-col gap-2 border-b border-line py-4 last:border-b-0 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="flex items-center gap-2.5">
        <span
          aria-hidden="true"
          className={`size-1.5 shrink-0 rounded-full ${tone.dot}`}
        />
        <span className="text-sm font-medium text-foreground">{row.label}</span>
      </div>
      <div className="sm:max-w-md sm:text-right">
        <p className={`text-sm font-medium ${tone.text}`}>{row.value}</p>
        <p className="mt-1 text-xs leading-5 text-muted">{row.detail}</p>
      </div>
    </div>
  );
}

export function CapabilitiesSection() {
  return (
    <section
      id="platform"
      aria-labelledby="platform-heading"
      className="border-t border-line"
    >
      <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="max-w-2xl">
          <Eyebrow>Platform</Eyebrow>
          <h2
            id="platform-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            An integrated urban response workspace
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            Six connected capabilities — from a validated incident report to a
            governed, explainable view of what may need attention.
          </p>
        </div>

        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-12">
          {capabilities.map((capability, index) => {
            const featured = index === 0;
            const span =
              index === 0
                ? "lg:col-span-6"
                : index === 1 || index === 2
                  ? "lg:col-span-3"
                  : "lg:col-span-4";
            return (
              <article
                key={capability.id}
                className={`group flex flex-col rounded-xl border border-line bg-surface p-5 transition hover:border-line/70 hover:bg-surface-raised sm:p-6 ${span}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg border border-accent/15 bg-accent/5 text-accent">
                    <LandingIcon
                      name={capability.icon}
                      className="size-[18px]"
                    />
                  </span>
                  <span className="font-mono text-[10px] tracking-widest text-muted/70">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="mt-5 text-base font-semibold tracking-tight text-foreground">
                  {capability.title}
                </h3>
                <p className="mt-2 text-sm leading-6 text-muted">
                  {capability.description}
                </p>
                {featured ? (
                  <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-line pt-4 font-mono text-[10px] uppercase tracking-wider text-muted">
                    <span>Report</span>
                    <span aria-hidden="true" className="text-accent/70">
                      →
                    </span>
                    <span>Locate</span>
                    <span aria-hidden="true" className="text-accent/70">
                      →
                    </span>
                    <span>Review</span>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function WorkflowSection() {
  return (
    <section
      id="intelligence"
      aria-labelledby="intelligence-heading"
      className="border-t border-line bg-surface/30"
    >
      <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="max-w-2xl">
          <Eyebrow>Intelligence</Eyebrow>
          <h2
            id="intelligence-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            From report to review, one traceable path
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            Each stage builds on verified records and preserves context for the
            next. Analysis is explainable and bounded — the platform does not
            automatically dispatch or execute real-world actions.
          </p>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:flex lg:items-stretch lg:gap-0">
          {workflowSteps.map((step, index) => (
            <Fragment key={step.id}>
              <article className="rounded-xl border border-line bg-background/40 p-4 lg:min-w-0 lg:flex-1">
                <div className="flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-lg border border-accent/15 bg-accent/5 text-accent">
                    <LandingIcon name={step.icon} className="size-4" />
                  </span>
                  <span className="font-mono text-[10px] text-muted/70">
                    0{index + 1}
                  </span>
                </div>
                <h3 className="mt-4 text-sm font-semibold text-foreground">
                  {step.title}
                </h3>
                <p className="mt-2 text-xs leading-5 text-muted">
                  {step.description}
                </p>
              </article>
              {index < workflowSteps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="hidden w-8 shrink-0 items-center justify-center text-accent/50 lg:flex"
                >
                  <LandingIcon name="arrow" className="size-4" />
                </span>
              ) : null}
            </Fragment>
          ))}
        </div>

        <div className="mt-12">
          <PlatformPreview />
          <p className="mt-3 text-xs leading-5 text-muted">
            Interface preview is illustrative. It shows the shape of the
            authenticated workspace; records, counts and risk bands shown are
            examples, not live data.
          </p>
        </div>
      </div>
    </section>
  );
}

export function ArchitectureSection() {
  return (
    <section
      id="architecture"
      aria-labelledby="architecture-heading"
      className="border-t border-line"
    >
      <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="max-w-2xl">
          <Eyebrow>Architecture</Eyebrow>
          <h2
            id="architecture-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            Built on a clear, maintainable foundation
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            The technologies below reflect the implementation in this
            repository — no aspirational stack is presented as deployed.
          </p>
        </div>

        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {architectureLayers.map((layer, index) => (
            <article
              key={layer.id}
              className="relative overflow-hidden rounded-xl border border-line bg-surface p-5"
            >
              <span
                aria-hidden="true"
                className={`absolute inset-x-0 top-0 h-px ${index === 0 ? "bg-accent/60" : "bg-line"}`}
              />
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                {layer.label}
              </p>
              <h3 className="mt-4 text-lg font-semibold tracking-tight text-foreground">
                {layer.title}
              </h3>
              <p className="mt-2 text-sm leading-6 text-muted">{layer.detail}</p>
              <ul className="mt-5 flex flex-wrap gap-1.5">
                {layer.tags.map((tag) => (
                  <li
                    key={tag}
                    className="rounded-md border border-line bg-background/40 px-2 py-1 font-mono text-[10px] text-muted"
                  >
                    {tag}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <div className="mt-6 rounded-xl border border-line bg-surface/50 px-5 py-4 text-sm leading-6 text-muted">
          Authentication, role checks, row-level policies, spatial validation
          and evidence handling are foundational. Intelligence outputs remain
          research-oriented and no pilot is active.
        </div>
      </div>
    </section>
  );
}

export function TrustSection() {
  return (
    <section
      aria-labelledby="trust-heading"
      className="border-t border-line bg-surface/30"
    >
      <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="max-w-2xl">
          <Eyebrow>Trust &amp; governance</Eyebrow>
          <h2
            id="trust-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            Honest boundaries, not implied certainty
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            Implemented, research-oriented and externally dependent work are
            shown separately so that no experimental output is mistaken for a
            validated operational result.
          </p>
        </div>

        <div className="mt-10 grid gap-3 lg:grid-cols-3">
          {governanceTiers.map((tier) => (
            <TierCard key={tier.id} tier={tier} />
          ))}
        </div>
      </div>
    </section>
  );
}

export function PilotStatusSection() {
  return (
    <section
      id="pilot-status"
      aria-labelledby="pilot-status-heading"
      className="border-t border-line"
    >
      <div className="mx-auto w-full max-w-7xl px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
        <div className="max-w-2xl">
          <Eyebrow>Platform status</Eyebrow>
          <h2
            id="pilot-status-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            Platform development status
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            Research-oriented intelligence. Pilot activation is currently
            governed by validation and external evidence requirements.
          </p>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)] lg:items-start">
          <div className="rounded-xl border border-line bg-surface px-5 py-2 sm:px-6">
            {statusRows.map((row) => (
              <StatusItem key={row.id} row={row} />
            ))}
            <p className="border-t border-line py-4 text-xs leading-5 text-muted">
              The status above reflects repository state and local verification
              only. It does not assert production validation or operational
              deployment.
            </p>
          </div>

          <div>
            <BackendStatus />
            <p className="mt-3 px-1 text-xs leading-5 text-muted">
              This panel performs a real browser request to the configured API
              health endpoint. No status is pre-set or simulated.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function FinalCtaSection() {
  return (
    <section
      aria-labelledby="cta-heading"
      className="border-t border-line bg-gradient-to-br from-accent/[0.06] via-transparent to-accent-cyan/[0.04]"
    >
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-5 py-16 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-10 lg:py-20">
        <div className="max-w-2xl">
          <Eyebrow>Get started</Eyebrow>
          <h2
            id="cta-heading"
            className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl"
          >
            {finalCta.headline}
          </h2>
          <p className="mt-4 text-sm leading-6 text-muted">
            {finalCta.description}
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row lg:shrink-0">
          <Link
            href={finalCta.primary.href}
            className="group inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-background transition hover:bg-accent/90"
          >
            {finalCta.primary.label}
            <LandingIcon name="arrow" className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href={finalCta.secondary.href}
            className="inline-flex items-center justify-center rounded-lg border border-line bg-surface px-5 py-3 text-sm font-medium text-foreground transition hover:bg-surface-raised"
          >
            {finalCta.secondary.label}
          </Link>
        </div>
      </div>
    </section>
  );
}
