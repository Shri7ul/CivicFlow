/**
 * Single source of truth for public landing-page copy and link targets.
 *
 * Keeping this data separate from presentation lets the route audit assert
 * that every anchor and CTA resolves to a real section or a valid public
 * route. Descriptions describe capabilities that exist in the codebase;
 * research-oriented behaviour is stated explicitly rather than presented as
 * validated prediction or operational execution.
 */

/** Static so the public page can be prerendered without reading current time. */
export const copyrightYear = 2026;

export type LandingLink = {
  label: string;
  href: string;
};

export type LandingSection = {
  id: string;
  label: string;
};

export type Capability = {
  id: string;
  title: string;
  description: string;
  icon: "incident" | "geo" | "risk" | "decision" | "evidence" | "governance";
};

export type WorkflowStep = {
  id: string;
  title: string;
  description: string;
  icon: "report" | "locate" | "analyze" | "plan" | "review";
};

export type ArchitectureLayer = {
  id: string;
  label: string;
  title: string;
  detail: string;
  tags: readonly string[];
};

export type GovernanceTier = {
  id: string;
  label: string;
  tone: "implemented" | "research" | "external";
  summary: string;
  items: readonly string[];
};

export type StatusRow = {
  id: string;
  label: string;
  value: string;
  tone: "implemented" | "research" | "inactive";
  detail: string;
};

/** Sections that the primary navigation links to, in document order. */
export const landingSections = [
  { id: "platform", label: "Platform" },
  { id: "intelligence", label: "Intelligence" },
  { id: "architecture", label: "Architecture" },
  { id: "pilot-status", label: "Pilot Status" },
] as const satisfies readonly LandingSection[];

export const landingNavLinks: readonly LandingLink[] = landingSections.map(
  ({ id, label }) => ({ label, href: `#${id}` }),
);

/** Routes that are safe to link to from a public, unauthenticated page. */
export const publicRoutes = [
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/update-password",
] as const;

export const landingFooterLinks: readonly LandingLink[] = [
  { label: "Platform", href: "#platform" },
  { label: "Intelligence", href: "#intelligence" },
  { label: "Architecture", href: "#architecture" },
  { label: "Platform status", href: "#pilot-status" },
  { label: "Sign in", href: "/login" },
];

export const hero = {
  eyebrow: "Urban response intelligence",
  headlineLead: "Understand urban incidents.",
  headlineAccent: "Coordinate smarter responses.",
  description:
    "CivicFlow brings incident reporting, spatial intelligence, operational workflows and governed decision-support into one unified urban response platform.",
  primary: { label: "Explore the platform", href: "#platform" },
  secondary: { label: "View architecture", href: "#architecture" },
  assurances: [
    "Role-aware access",
    "Explainable analysis",
    "Governed workflows",
  ],
} as const;

export const capabilities: readonly Capability[] = [
  {
    id: "incident-operations",
    title: "Incident operations",
    description:
      "Capture validated coordinates, category, severity and description. Citizens see only their own reports; authorized staff work a visibility-scoped queue. Every status change is recorded in an immutable history.",
    icon: "incident",
  },
  {
    id: "geographic-intelligence",
    title: "Geographic intelligence",
    description:
      "MapLibre renders incident locations with viewport queries and clustering. PostGIS geography, GIST indexes and H3 cells provide spatial filtering and location context.",
    icon: "geo",
  },
  {
    id: "risk-intelligence",
    title: "Risk intelligence",
    description:
      "Versioned H3 risk bands combine severity, density, recency, category and exposure factors into explainable components and trends. Outputs are research-oriented and need authoritative data.",
    icon: "risk",
  },
  {
    id: "decision-support",
    title: "Decision support",
    description:
      "Staff-only scenarios model explicit actions, dependencies, budgets and constraints. Bounded scheduling heuristics compare strategies without dispatching or reserving anything.",
    icon: "decision",
  },
  {
    id: "evidence-management",
    title: "Evidence management",
    description:
      "Validated image uploads are stored privately and exposed through short-lived signed previews, with provenance and review workflows for authorized staff.",
    icon: "evidence",
  },
  {
    id: "governance",
    title: "Governance",
    description:
      "Signed JWT verification, exactly three roles, idempotent Citizen provisioning, audited role changes, row-level policies and validation workflows define clear boundaries.",
    icon: "governance",
  },
];

export const workflowSteps: readonly WorkflowStep[] = [
  {
    id: "report",
    title: "Report",
    description:
      "A validated incident record is created with category, severity, description and an explicit map position.",
    icon: "report",
  },
  {
    id: "locate",
    title: "Locate",
    description:
      "PostGIS geography and H3 indexing place the report in spatial context for map and area queries.",
    icon: "locate",
  },
  {
    id: "analyze",
    title: "Analyze",
    description:
      "Explainable signals and versioned risk bands summarize spatial and temporal patterns — research-oriented, not predictive truth.",
    icon: "analyze",
  },
  {
    id: "plan",
    title: "Plan",
    description:
      "Staff explore bounded scenarios with explicit constraints. No automated dispatch or real-world execution takes place.",
    icon: "plan",
  },
  {
    id: "review",
    title: "Review",
    description:
      "Status transitions, evidence, decisions and validation runs remain auditable for authorized roles.",
    icon: "review",
  },
];

export const architectureLayers: readonly ArchitectureLayer[] = [
  {
    id: "frontend",
    label: "Interface",
    title: "Next.js",
    detail:
      "Protected workspace, incident queue and maps built with TypeScript and MapLibre GL.",
    tags: ["Next.js", "TypeScript", "MapLibre"],
  },
  {
    id: "backend",
    label: "Service",
    title: "FastAPI",
    detail:
      "Versioned APIs for incidents, spatial analysis, risk, planning and governance with verified JWTs and role checks.",
    tags: ["Python", "FastAPI", "RBAC"],
  },
  {
    id: "database",
    label: "Data",
    title: "PostgreSQL",
    detail:
      "PostGIS geography, GIST indexes and Alembic-managed schema with row-level policies.",
    tags: ["PostgreSQL", "PostGIS", "Alembic"],
  },
  {
    id: "infrastructure",
    label: "Platform",
    title: "Supabase",
    detail:
      "Authentication, database and private object storage used by the application where applicable.",
    tags: ["Auth", "Storage", "Database"],
  },
];

export const governanceTiers: readonly GovernanceTier[] = [
  {
    id: "implemented",
    label: "Implemented",
    tone: "implemented",
    summary: "Available in the application and covered by the local test suite.",
    items: [
      "Authenticated API workflows with verified JWTs",
      "Role-aware navigation with independent backend enforcement",
      "Incident lifecycle, ownership and immutable status history",
      "Private evidence with short-lived signed previews",
    ],
  },
  {
    id: "research",
    label: "Research-oriented",
    tone: "research",
    summary: "Explainable and bounded; requires authoritative data to be meaningful.",
    items: [
      "H3 risk bands, trends and exposure factors",
      "Deterministic incident-intelligence signals",
      "Bounded planning simulation and strategy comparison",
      "Persisted validation experiments and labelled metrics",
    ],
  },
  {
    id: "external",
    label: "Externally dependent",
    tone: "external",
    summary: "Not claimed as available until the required evidence or access exists.",
    items: [
      "Authoritative municipal outcome and asset datasets",
      "Licensed live feeds and external notification delivery",
      "Field-calibrated outcome evaluation and pilot activation",
      "Department and administrative management",
    ],
  },
];

export const statusRows: readonly StatusRow[] = [
  {
    id: "core",
    label: "Core application",
    value: "Implemented",
    tone: "implemented",
    detail: "Backend and frontend suites run locally; no production E2E is claimed.",
  },
  {
    id: "intelligence",
    label: "Intelligence outputs",
    value: "Research-oriented",
    tone: "research",
    detail: "Explainable and bounded. No validated predictive model is asserted.",
  },
  {
    id: "pilot",
    label: "Pilot activation",
    value: "Not active",
    tone: "inactive",
    detail:
      "Governed by validation and external evidence requirements. No municipal partnership, ground-truth validation or operational deployment is claimed.",
  },
];

export const finalCta = {
  headline: "Bring urban response workflows into one workspace.",
  description:
    "Start with incident reporting and a role-scoped workspace. Intelligence features remain transparent about their research status and data requirements.",
  primary: { label: "Create account", href: "/signup" },
  secondary: { label: "Explore platform", href: "#platform" },
} as const;
