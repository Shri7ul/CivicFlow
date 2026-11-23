"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import {
  getIncidentIntelligence,
  reviewIncidentRelationship,
} from "@/lib/api/intelligence";
import {
  candidateLabel,
  confidenceTone,
  formatConfidence,
  formatDistance,
  impactTypeLabels,
  relationshipStatusLabels,
  relationshipTypeLabels,
} from "@/lib/intelligence";
import { formatDateTime } from "@/lib/incidents";
import type {
  IncidentCandidate,
  IncidentIntelligence,
  IncidentRelationship,
  RelationshipStatus,
  RelationshipType,
} from "@/types/intelligence";

type IncidentIntelligencePanelProps = {
  incidentId: string;
  canReview: boolean;
};

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "Unable to load incident intelligence.";
}

function SignalDetails({ candidate }: { candidate: IncidentCandidate }) {
  return (
    <details className="mt-3 rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
        Why this suggestion?
      </summary>
      <ul className="mt-3 space-y-2">
        {candidate.signals.map((signal) => (
          <li key={signal.key} className="text-xs text-slate-400">
            <span className="font-medium text-slate-200">{signal.label}:</span>{" "}
            {signal.explanation}{" "}
            <span className="font-mono text-[10px] text-slate-500">
              +{(signal.contribution * 100).toFixed(0)} pts
            </span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function CandidateCard({
  candidate,
  kind,
  canReview,
  reviewing,
  onReview,
}: {
  candidate: IncidentCandidate;
  kind: "duplicate" | "related";
  canReview: boolean;
  reviewing: string | null;
  onReview: (
    candidate: IncidentCandidate,
    type: RelationshipType,
    status: RelationshipStatus,
  ) => void;
}) {
  const reviewKey = `${candidate.incident.id}:${kind}`;
  return (
    <li className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            href={`/incidents/${candidate.incident.id}`}
            className="text-sm font-semibold text-white underline-offset-4 hover:underline"
          >
            {candidate.incident.title}
          </Link>
          <p className="mt-1 text-[11px] text-slate-500">
            {candidateLabel(candidate)}
          </p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${confidenceTone(
            candidate.confidence,
          )}`}
        >
          {formatConfidence(candidate.confidence)}
        </span>
      </div>
      {candidate.reasons.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {candidate.reasons.map((reason) => (
            <li
              key={reason}
              className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300"
            >
              {reason}
            </li>
          ))}
        </ul>
      ) : null}
      <SignalDetails candidate={candidate} />
      {canReview ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={reviewing !== null}
            onClick={() =>
              onReview(
                candidate,
                kind === "duplicate" ? "DUPLICATE" : "RELATED",
                "CONFIRMED",
              )
            }
            className="rounded-lg bg-emerald-400 px-3 py-1.5 text-[11px] font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
          >
            {reviewing === reviewKey
              ? "Saving…"
              : kind === "duplicate"
                ? "Confirm duplicate"
                : "Confirm related"}
          </button>
          <button
            type="button"
            disabled={reviewing !== null}
            onClick={() =>
              onReview(
                candidate,
                kind === "duplicate" ? "DUPLICATE" : "RELATED",
                "DISMISSED",
              )
            }
            className="rounded-lg border border-white/15 px-3 py-1.5 text-[11px] text-slate-300 transition hover:border-white/25 disabled:opacity-50"
          >
            Dismiss
          </button>
          <span className="self-center text-[10px] text-slate-500">
            A review is recorded; incidents are never merged.
          </span>
        </div>
      ) : null}
    </li>
  );
}

function RelationshipCard({
  relationship,
}: {
  relationship: IncidentRelationship;
}) {
  return (
    <li className="rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.04] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href={`/incidents/${relationship.other_incident.id}`}
            className="text-sm font-semibold text-white underline-offset-4 hover:underline"
          >
            {relationship.other_incident.title}
          </Link>
          <p className="mt-1 text-[11px] text-slate-400">
            {relationshipTypeLabels[relationship.relationship_type]} ·{" "}
            {relationshipStatusLabels[relationship.status]} ·{" "}
            {formatConfidence(relationship.confidence)} confidence
          </p>
        </div>
        <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-200">
          Human review
        </span>
      </div>
      {relationship.note ? (
        <p className="mt-2 text-xs leading-5 text-slate-300">
          {relationship.note}
        </p>
      ) : null}
      {relationship.reviewed_at ? (
        <p className="mt-2 text-[10px] text-slate-500">
          Reviewed {formatDateTime(relationship.reviewed_at)}
        </p>
      ) : null}
    </li>
  );
}

export function IncidentIntelligencePanel({
  incidentId,
  canReview,
}: IncidentIntelligencePanelProps) {
  const { apiRequest } = useAuth();
  const [data, setData] = useState<IncidentIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setError(null);
      try {
        const next = await getIncidentIntelligence(apiRequest, incidentId, {
          signal,
        });
        if (requestId !== requestIdRef.current) {
          return;
        }
        setData(next);
      } catch (loadError) {
        if (
          loadError instanceof Error &&
          "code" in loadError &&
          (loadError as { code?: string }).code === "request_cancelled"
        ) {
          return;
        }
        if (requestId !== requestIdRef.current) {
          return;
        }
        setError(errorMessage(loadError));
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [apiRequest, incidentId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void load(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  async function review(
    candidate: IncidentCandidate,
    relationshipType: RelationshipType,
    status: RelationshipStatus,
  ) {
    setReviewing(`${candidate.incident.id}:${relationshipType === "DUPLICATE" ? "duplicate" : "related"}`);
    setReviewError(null);
    try {
      await reviewIncidentRelationship(apiRequest, incidentId, {
        other_incident_id: candidate.incident.id,
        relationship_type: relationshipType,
        status,
        confidence: candidate.confidence,
        signals: {
          source: "incident_intelligence",
          reasons: candidate.reasons,
        },
        note:
          status === "CONFIRMED"
            ? `Staff confirmed a ${relationshipType.toLowerCase()} suggestion from the intelligence engine.`
            : `Staff dismissed a ${relationshipType.toLowerCase()} suggestion from the intelligence engine.`,
      });
      await load();
    } catch (reviewFailure) {
      setReviewError(errorMessage(reviewFailure));
    } finally {
      setReviewing(null);
    }
  }

  const confirmed = (data?.confirmed_relationships ?? []).filter(
    (relationship) => relationship.status === "CONFIRMED",
  );
  const dismissed = (data?.confirmed_relationships ?? []).filter(
    (relationship) => relationship.status === "DISMISSED",
  );
  // Once a reviewer has confirmed or dismissed a suggestion, don't present it
  // as an unreviewed suggestion again. Re-review remains available through the
  // API, while the UI keeps the reviewer's decision visible.
  const reviewedKeys = new Set(
    (data?.confirmed_relationships ?? []).map(
      (relationship) =>
        `${relationship.other_incident.id}:${relationship.relationship_type}`,
    ),
  );
  const duplicateCandidates = (data?.duplicate_candidates ?? []).filter(
    (candidate) => !reviewedKeys.has(`${candidate.incident.id}:DUPLICATE`),
  );
  const relatedCandidates = (data?.related_candidates ?? []).filter(
    (candidate) => !reviewedKeys.has(`${candidate.incident.id}:RELATED`),
  );

  return (
    <section
      id="intelligence"
      className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8"
      aria-labelledby="intelligence-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="intelligence-heading"
            className="text-sm font-semibold text-white"
          >
            Incident intelligence
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-400">
            Explainable suggestions from nearby reports, infrastructure
            proximity, and dependency links. Suggestions are not facts until a
            worker or administrator confirms them.
          </p>
        </div>
        <span className="rounded-full border border-sky-300/20 bg-sky-300/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sky-200">
          Decision support
        </span>
      </div>

      {loading && !data ? (
        <div className="mt-5 space-y-3" aria-label="Loading intelligence">
          <div className="h-20 animate-pulse rounded-2xl bg-white/[0.04]" />
          <div className="h-20 animate-pulse rounded-2xl bg-white/[0.04]" />
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-300/5 p-4"
        >
          <p className="text-sm text-rose-100">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="mt-3 rounded-lg border border-white/15 px-3 py-1.5 text-xs text-white"
          >
            Retry intelligence
          </button>
        </div>
      ) : null}

      {data && !error ? (
        <>
          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <section>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Possible duplicates
                </h3>
                <span className="text-[10px] text-slate-500">
                  suggestions
                </span>
              </div>
              {duplicateCandidates.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">
                  No duplicate candidates matched the configured distance, time,
                  text, category, and confidence thresholds.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {duplicateCandidates.map((candidate) => (
                    <CandidateCard
                      key={candidate.incident.id}
                      candidate={candidate}
                      kind="duplicate"
                      canReview={canReview}
                      reviewing={reviewing}
                      onReview={(item, type, status) =>
                        void review(item, type, status)
                      }
                    />
                  ))}
                </ul>
              )}
            </section>

            <section>
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Possibly related
                </h3>
                <span className="text-[10px] text-slate-500">
                  suggestions
                </span>
              </div>
              {relatedCandidates.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">
                  No related reports crossed the confidence threshold.
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {relatedCandidates.map((candidate) => (
                    <CandidateCard
                      key={candidate.incident.id}
                      candidate={candidate}
                      kind="related"
                      canReview={canReview}
                      reviewing={reviewing}
                      onReview={(item, type, status) =>
                        void review(item, type, status)
                      }
                    />
                  ))}
                </ul>
              )}
            </section>
          </div>

          {reviewError ? (
            <p role="alert" className="mt-4 text-xs text-rose-200">
              {reviewError}
            </p>
          ) : null}

          <section className="mt-6">
            <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
              Staff-reviewed relationships
            </h3>
            {confirmed.length === 0 && dismissed.length === 0 ? (
              <p className="mt-3 rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">
                No relationships have been reviewed yet.
              </p>
            ) : (
              <ul className="mt-3 grid gap-3 sm:grid-cols-2">
                {[...confirmed, ...dismissed].map((relationship) => (
                  <RelationshipCard
                    key={relationship.id}
                    relationship={relationship}
                  />
                ))}
              </ul>
            )}
          </section>

          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                Nearby infrastructure
              </h3>
              {data.infrastructure.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">
                  No active infrastructure assets are within the configured
                  radius. No external municipal asset feed is configured.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {data.infrastructure.map((item) => (
                    <li
                      key={item.asset.id}
                      className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2.5"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-xs font-semibold text-slate-100">
                            {item.asset.name}
                          </p>
                          <p className="mt-0.5 text-[10px] text-slate-500">
                            {item.asset.asset_type} ·{" "}
                            {formatDistance(item.distance_m)} away ·{" "}
                            {item.dependency_count} dependency link
                            {item.dependency_count === 1 ? "" : "s"}
                          </p>
                        </div>
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
                          spatial association
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                Potential impact paths
              </h3>
              {data.potential_impacts.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-white/10 p-4 text-xs text-slate-500">
                  No infrastructure dependency paths are available for this
                  location.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {data.potential_impacts.map((impact, index) => (
                    <li
                      key={`${impact.root_asset.id}-${impact.affected_asset.id}-${index}`}
                      className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2.5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-xs font-semibold text-slate-100">
                            {impact.path.map((asset) => asset.name).join(" → ")}
                          </p>
                          <p className="mt-0.5 text-[10px] text-slate-500">
                            {impactTypeLabels[impact.impact_type]} ·{" "}
                            {formatConfidence(impact.confidence)} confidence ·
                            depth {impact.depth}
                          </p>
                        </div>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[10px] ${
                            impact.impact_type === "GEOSPATIAL_ASSOCIATION"
                              ? "border-sky-300/20 bg-sky-300/10 text-sky-200"
                              : "border-amber-300/20 bg-amber-300/10 text-amber-100"
                          }`}
                        >
                          {impactTypeLabels[impact.impact_type]}
                        </span>
                      </div>
                      <p className="mt-2 text-[11px] leading-5 text-slate-400">
                        {impact.rationale}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <details className="mt-6 rounded-xl border border-white/10 bg-slate-950/30 px-4 py-3">
            <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
              Data limits and thresholds
            </summary>
            <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[11px] leading-5 text-slate-400">
              {data.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
            <dl className="mt-3 grid gap-2 text-[10px] text-slate-500 sm:grid-cols-2">
              {Object.entries(data.thresholds).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-3">
                  <dt className="font-mono">{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-[10px] text-slate-500">
              Generated {formatDateTime(data.generated_at)}.
            </p>
          </details>
        </>
      ) : null}
    </section>
  );
}
