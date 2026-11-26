import { describe, expect, it } from "vitest";

import {
  architectureLayers,
  capabilities,
  finalCta,
  governanceTiers,
  hero,
  landingFooterLinks,
  landingNavLinks,
  landingSections,
  publicRoutes,
  statusRows,
  workflowSteps,
  type LandingLink,
} from "./landing-content";

const allLinks: readonly LandingLink[] = [
  ...landingNavLinks,
  ...landingFooterLinks,
  hero.primary,
  hero.secondary,
  finalCta.primary,
  finalCta.secondary,
];

function copyStrings(): string[] {
  return [
    hero.eyebrow,
    hero.headlineLead,
    hero.headlineAccent,
    hero.description,
    ...hero.assurances,
    ...capabilities.flatMap((item) => [item.title, item.description]),
    ...workflowSteps.flatMap((item) => [item.title, item.description]),
    ...architectureLayers.flatMap((item) => [item.title, item.detail]),
    ...governanceTiers.flatMap((item) => [item.label, item.summary, ...item.items]),
    ...statusRows.flatMap((item) => [item.label, item.value, item.detail]),
    finalCta.headline,
    finalCta.description,
  ];
}

describe("landing navigation integrity", () => {
  const sectionIds = new Set<string>(
    landingSections.map((section) => section.id),
  );

  it("declares unique section ids", () => {
    expect(sectionIds.size).toBe(landingSections.length);
  });

  it("resolves every in-page link to a real section", () => {
    for (const link of allLinks) {
      if (!link.href.startsWith("#")) continue;
      expect(sectionIds.has(link.href.slice(1)), link.href).toBe(true);
    }
  });

  it("points every route link to an existing public route", () => {
    for (const link of allLinks) {
      if (link.href.startsWith("#")) continue;
      expect(publicRoutes as readonly string[]).toContain(link.href);
    }
  });

  it("keeps the primary navigation in document order", () => {
    const order = landingSections.map((section) => section.id);
    const navTargets = landingNavLinks.map((link) => link.href.slice(1));
    expect(navTargets).toEqual(order);
  });
});

describe("landing content structure", () => {
  it("renders the requested section counts", () => {
    expect(capabilities).toHaveLength(6);
    expect(workflowSteps).toHaveLength(5);
    expect(architectureLayers).toHaveLength(4);
    expect(governanceTiers).toHaveLength(3);
    expect(statusRows).toHaveLength(3);
  });

  it("uses unique ids for every repeated item", () => {
    for (const items of [capabilities, workflowSteps, architectureLayers]) {
      expect(new Set(items.map((item) => item.id)).size).toBe(items.length);
    }
  });
});

describe("landing copy honesty", () => {
  it("does not present fabricated scale or accuracy statistics", () => {
    for (const copy of copyStrings()) {
      expect(copy).not.toMatch(/\b\d+(?:\.\d+)?\s*%/);
      expect(copy).not.toMatch(/\b(?:thousands|millions|hundreds)\s+of\b/i);
    }
  });

  it("states that pilot activation is not active", () => {
    const pilot = statusRows.find((row) => row.id === "pilot");
    expect(pilot?.value).toBe("Not active");
    expect(pilot?.detail).toContain("external evidence");
  });

  it("labels research-oriented work explicitly", () => {
    const research = governanceTiers.find((tier) => tier.id === "research");
    expect(research?.label).toBe("Research-oriented");
    expect(research?.summary).toContain("authoritative data");
  });

  it("does not claim automated dispatch or real-world execution", () => {
    for (const copy of copyStrings()) {
      expect(copy.toLowerCase()).not.toContain("automated dispatch takes place");
    }
    const plan = workflowSteps.find((step) => step.id === "plan");
    expect(plan?.description).toContain("No automated dispatch");
  });
});
