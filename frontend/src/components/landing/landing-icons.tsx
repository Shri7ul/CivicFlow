import type { ReactNode, SVGProps } from "react";

export type LandingIconName =
  | "incident"
  | "geo"
  | "risk"
  | "decision"
  | "evidence"
  | "governance"
  | "report"
  | "locate"
  | "analyze"
  | "plan"
  | "review"
  | "arrow";

type IconProps = SVGProps<SVGSVGElement> & {
  name: LandingIconName;
};

/**
 * Compact, single-weight line icons. Each glyph maps to a real product
 * concept; there are no decorative-only icons on the landing page.
 */
export function LandingIcon({ name, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}

const paths: Record<LandingIconName, ReactNode> = {
  incident: (
    <>
      <path d="M12 3.5 3.8 17.2A1.4 1.4 0 0 0 5 19.3h14a1.4 1.4 0 0 0 1.2-2.1L12 3.5Z" />
      <path d="M12 9v4.2M12 16.4h.01" />
    </>
  ),
  geo: (
    <>
      <path d="M12 21s6.5-5.6 6.5-11a6.5 6.5 0 1 0-13 0C5.5 15.4 12 21 12 21Z" />
      <circle cx="12" cy="10" r="2.4" />
    </>
  ),
  risk: (
    <>
      <path d="M4 6.5 12 3l8 3.5-8 3.5-8-3.5Z" />
      <path d="m4 12 8 3.5 8-3.5M4 17.5 12 21l8-3.5" />
    </>
  ),
  decision: (
    <>
      <path d="M5 4v5.5A3.5 3.5 0 0 0 8.5 13H12" />
      <path d="M5 20v-5.5A3.5 3.5 0 0 1 8.5 11H12" />
      <path d="M19 12h-7" />
      <circle cx="19" cy="12" r="1.6" />
    </>
  ),
  evidence: (
    <>
      <rect x="3.5" y="5" width="17" height="14" rx="2" />
      <path d="m3.5 16 4.8-4.4a1.6 1.6 0 0 1 2.2 0l3 2.8 2.1-1.9a1.6 1.6 0 0 1 2.2 0l2.7 2.5" />
      <circle cx="9" cy="9.5" r="1.3" />
    </>
  ),
  governance: (
    <>
      <path d="M12 3 5 5.8v5.4c0 4.2 2.8 7.6 7 9.3 4.2-1.7 7-5.1 7-9.3V5.8L12 3Z" />
      <path d="m9.2 12 1.9 1.9 3.7-3.8" />
    </>
  ),
  report: (
    <>
      <path d="M7 3.5h7l4 4v13H7a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z" />
      <path d="M14 3.5v4h4M9 12h6M9 15.5h6" />
    </>
  ),
  locate: (
    <>
      <circle cx="12" cy="12" r="3" />
      <circle cx="12" cy="12" r="7.5" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22" />
    </>
  ),
  analyze: (
    <>
      <path d="M4 19.5h16" />
      <path d="M6.5 19.5V11M11 19.5V5.5M15.5 19.5v-7M20 19.5V8.5" />
    </>
  ),
  plan: (
    <>
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
      <path d="M3.5 9.5h17M9 9.5v10" />
      <path d="m12 14 1.8 1.8L17 12.6" />
    </>
  ),
  review: (
    <>
      <path d="M4 5.5h16v13H4z" />
      <path d="M8 10h8M8 13.5h8M8 17h4" />
    </>
  ),
  arrow: <path d="M4 12h15m-5-5 5 5-5 5" />,
};
