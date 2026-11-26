import type { CSSProperties } from "react";

/**
 * Static product previews for the public page. These are intentionally not
 * backed by the live API: they must never trigger database reads/writes or
 * imply that example records are real production incidents. Every preview is
 * labelled "Illustrative preview" in the rendered UI and documented as such.
 */

const mapGrid: CSSProperties = {
  backgroundColor: "#0b1118",
  backgroundImage:
    "linear-gradient(rgba(27,39,51,0.85) 1px, transparent 1px), linear-gradient(90deg, rgba(27,39,51,0.85) 1px, transparent 1px)",
  backgroundSize: "26px 26px",
};

type Marker = {
  left: string;
  top: string;
  tone: string;
  ring?: string;
};

const markers: readonly Marker[] = [
  { left: "22%", top: "30%", tone: "bg-rose-400", ring: "ring-rose-400/20" },
  { left: "48%", top: "22%", tone: "bg-amber-300" },
  { left: "64%", top: "48%", tone: "bg-accent", ring: "ring-accent/25" },
  { left: "34%", top: "64%", tone: "bg-accent-cyan" },
  { left: "78%", top: "72%", tone: "bg-amber-300" },
];

const queueRows = [
  { id: "INC-2048", title: "Road obstruction", status: "In review", dot: "bg-amber-300" },
  { id: "INC-2047", title: "Flooding report", status: "Open", dot: "bg-rose-400" },
  { id: "INC-2046", title: "Street lighting", status: "Resolved", dot: "bg-accent" },
] as const;

const riskBars = [
  "bg-accent",
  "bg-accent",
  "bg-accent-cyan",
  "bg-amber-300",
  "bg-accent",
  "bg-rose-400/80",
] as const;

function MapMarkers({ compact = false }: { compact?: boolean }) {
  return (
    <>
      {markers.map((marker) => (
        <span
          key={`${marker.left}-${marker.top}`}
          aria-hidden="true"
          className={`absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-background/60 ${marker.tone} ${
            marker.ring ? `ring-4 ${marker.ring}` : ""
          } ${compact ? "size-2" : ""}`}
          style={{ left: marker.left, top: marker.top }}
        />
      ))}
    </>
  );
}

function PreviewLabel() {
  return (
    <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
      Illustrative preview
    </span>
  );
}

export function HeroProductPreview() {
  return (
    <div className="rounded-2xl border border-line bg-surface-raised/80 p-1.5 shadow-2xl shadow-black/50">
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="size-2 rounded-sm bg-accent" />
            <span className="text-xs font-medium text-foreground">
              Incident overview
            </span>
          </div>
          <PreviewLabel />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          <div
            className="relative h-[200px] overflow-hidden border-b border-line sm:h-[286px] sm:border-b-0 sm:border-r"
            style={mapGrid}
          >
            <span
              aria-hidden="true"
              className="absolute inset-x-[12%] top-[46%] h-px -rotate-6 bg-accent-cyan/15"
            />
            <span
              aria-hidden="true"
              className="absolute inset-y-[8%] left-[54%] w-px rotate-3 bg-accent-cyan/10"
            />
            <MapMarkers />
            <div className="absolute bottom-3 left-3 right-3 rounded-lg border border-line bg-background/90 px-3 py-2 backdrop-blur">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] text-muted">
                  INC-2048
                </span>
                <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[10px] text-amber-200">
                  In review
                </span>
              </div>
              <p className="mt-1 text-xs font-medium text-foreground">
                Road obstruction · selected incident
              </p>
            </div>
          </div>

          <div className="hidden flex-col sm:flex">
            <div className="flex items-center justify-between border-b border-line px-3.5 py-2.5">
              <span className="text-xs font-medium text-foreground">
                Incident queue
              </span>
              <span className="font-mono text-[10px] text-muted">03 shown</span>
            </div>
            <ul className="flex-1 divide-y divide-line">
              {queueRows.map((row) => (
                <li key={row.id} className="px-3.5 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`size-1.5 shrink-0 rounded-full ${row.dot}`}
                    />
                    <span className="font-mono text-[10px] text-muted">
                      {row.id}
                    </span>
                    <span className="ml-auto text-[10px] text-muted">
                      {row.status}
                    </span>
                  </div>
                  <p className="mt-1.5 truncate text-xs text-foreground">
                    {row.title}
                  </p>
                </li>
              ))}
            </ul>
            <div className="border-t border-line px-3.5 py-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted">Risk bands</span>
                <span className="font-mono text-[10px] text-muted">H3</span>
              </div>
              <div className="mt-2 flex gap-1">
                {riskBars.map((tone, index) => (
                  <span
                    key={index}
                    aria-hidden="true"
                    className={`h-5 flex-1 rounded-sm opacity-80 ${tone}`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5">
          <div className="flex gap-3 text-[10px] text-muted">
            <span>Open 02</span>
            <span>In review 01</span>
            <span>Resolved 01</span>
          </div>
          <span className="text-[10px] text-muted">Example view</span>
        </div>
      </div>
    </div>
  );
}

const workspaceSections = ["Overview", "Incidents", "Map", "Risk", "Decisions"];

export function PlatformPreview() {
  return (
    <div className="rounded-2xl border border-line bg-surface-raised/60 p-1.5 shadow-2xl shadow-black/30">
      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="size-2 rounded-sm bg-accent" />
            <span className="text-xs font-medium text-foreground">
              CivicFlow workspace
            </span>
            <span className="hidden text-[10px] text-muted sm:inline">
              / operations overview
            </span>
          </div>
          <PreviewLabel />
        </div>

        <div className="grid grid-cols-[52px_minmax(0,1fr)] sm:grid-cols-[168px_minmax(0,1fr)]">
          <aside className="border-r border-line bg-background/40 py-3">
            <ul className="flex flex-col gap-1 px-1.5 sm:px-2.5">
              {workspaceSections.map((section, index) => (
                <li key={section}>
                  <span
                    className={`flex items-center gap-2 rounded-md px-2 py-2 text-[10px] sm:px-2.5 sm:text-xs ${
                      index === 0
                        ? "bg-accent/10 text-accent"
                        : "text-muted"
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`size-1.5 shrink-0 rounded-sm ${
                        index === 0 ? "bg-accent" : "bg-muted/50"
                      }`}
                    />
                    <span className="hidden truncate sm:inline">{section}</span>
                  </span>
                </li>
              ))}
            </ul>
            <div className="mx-2.5 mt-4 hidden border-t border-line pt-3 sm:block">
              <p className="font-mono text-[9px] uppercase tracking-widest text-muted">
                Access
              </p>
              <p className="mt-1 text-[10px] leading-4 text-muted">
                Role-scoped views
              </p>
            </div>
          </aside>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5 sm:px-4">
              <span className="text-xs font-medium text-foreground">
                Incident queue
              </span>
              {["All", "Open", "In review"].map((chip) => (
                <span
                  key={chip}
                  className="rounded-md border border-line bg-surface-raised px-2 py-0.5 text-[10px] text-muted"
                >
                  {chip}
                </span>
              ))}
              <span className="ml-auto hidden font-mono text-[10px] text-muted sm:inline">
                visibility-scoped
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
              <div
                className="relative h-[200px] overflow-hidden border-b border-line md:h-[250px] md:border-b-0 md:border-r"
                style={mapGrid}
              >
                <span
                  aria-hidden="true"
                  className="absolute inset-x-[8%] top-[58%] h-px rotate-6 bg-accent/15"
                />
                <MapMarkers compact />
              </div>

              <div className="divide-y divide-line">
                {queueRows.map((row) => (
                  <div key={row.id} className="px-3 py-2.5 sm:px-4">
                    <div className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className={`size-1.5 rounded-full ${row.dot}`}
                      />
                      <span className="font-mono text-[10px] text-muted">
                        {row.id}
                      </span>
                      <span className="ml-auto text-[10px] text-muted">
                        {row.status}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-foreground">
                      {row.title}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-line px-3 py-3 sm:px-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted">
                  Explainable risk components
                </span>
                <span className="font-mono text-[10px] text-muted">
                  research-oriented
                </span>
              </div>
              <div className="mt-2 flex gap-1.5">
                {riskBars.map((tone, index) => (
                  <span
                    key={index}
                    aria-hidden="true"
                    className={`h-4 flex-1 rounded-sm opacity-70 ${tone}`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
