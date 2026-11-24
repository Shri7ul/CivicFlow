"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { EvidenceWorkspace } from "@/components/pilot/evidence-workspace";
import {
  Card,
  EmptyState,
  ErrorNotice,
  LoadingBlock,
  ReadinessScorecard,
  StatusPill,
  formatDate,
  formatNumber,
  humanStatus,
} from "@/components/pilot/pilot-ui";
import {
  decideRiskReview,
  downloadRiskTrace,
  getCorrelationCandidates,
  getCorrelationMetrics,
  getInfrastructureCoverage,
  getInfrastructureSource,
  getInfrastructureSources,
  getPilot,
  getPilotReadiness,
  getPilots,
  getReadiness,
  getRiskReview,
  getRiskReviews,
  getRiskTrace,
  getSimulationAudit,
  getTraceRuns,
  reviewCorrelationCandidate,
  transitionPilot,
  validateInfrastructureSource,
} from "@/lib/api/pilot";
import type {
  CorrelationCandidate,
  CorrelationMetrics,
  InfrastructureCoverage,
  InfrastructureSource,
  Pilot,
  ReadinessReport,
  RiskReviewCase,
  RiskTrace,
  SimulationAudit,
  TraceRunSummary,
} from "@/types/pilot";

type TabKey =
  | "overview"
  | "pilots"
  | "reviews"
  | "correlation"
  | "traceability"
  | "infrastructure"
  | "simulation"
  | "evidence";

const TABS: { key: TabKey; label: string; hint: string }[] = [
  { key: "overview", label: "Readiness", hint: "Scorecard and gates" },
  { key: "pilots", label: "Pilots", hint: "Lifecycle and approval" },
  { key: "reviews", label: "Review queue", hint: "Human risk review" },
  { key: "correlation", label: "Correlation", hint: "Reviewer-labelled pairs" },
  { key: "traceability", label: "Traceability", hint: "Assessment provenance" },
  { key: "infrastructure", label: "Infrastructure", hint: "Registry metadata" },
  { key: "simulation", label: "Simulation", hint: "Constraint audit" },
  { key: "evidence", label: "Evidence", hint: "Ground truth and provenance" },
];

const REVIEW_ACTIONS: { status: string; label: string }[] = [
  { status: "IN_REVIEW", label: "Start review" },
  { status: "ACCEPTED", label: "Accept prediction" },
  { status: "REJECTED", label: "Reject prediction" },
  { status: "NEEDS_INVESTIGATION", label: "Flag for investigation" },
  { status: "NEEDS_MORE_DATA", label: "Request more data" },
];

const TRANSITION_LABELS: Record<string, string> = {
  SUBMIT: "Submit for approval",
  APPROVE: "Approve pilot",
  REJECT: "Reject pilot",
  ACTIVATE: "Activate pilot",
  PAUSE: "Pause pilot",
  RESUME: "Resume pilot",
  COMPLETE: "Complete pilot",
  ARCHIVE: "Archive pilot",
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed.";
}

export function normalizePilot(pilot: Pilot): Pilot {
  return {
    ...pilot,
    reviewers: pilot.reviewers ?? [],
    history: pilot.history ?? [],
    allowed_actions: pilot.allowed_actions ?? [],
  };
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function KeyValue({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-xs leading-relaxed text-slate-200">{value}</dd>
    </div>
  );
}

function Advice({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] px-4 py-3 text-[11px] leading-relaxed text-amber-100/80">
      {children}
    </p>
  );
}

export function PilotWorkspace() {
  const { apiRequest, profile } = useAuth();
  const [tab, setTab] = useState<TabKey>("overview");
  const isAdmin = profile?.role === "ADMIN";

  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);

  const [pilots, setPilots] = useState<Pilot[]>([]);
  const [pilotsError, setPilotsError] = useState<string | null>(null);
  const [selectedPilotId, setSelectedPilotId] = useState<string | null>(null);
  const [pilotDetail, setPilotDetail] = useState<Pilot | null>(null);
  const [pilotReadiness, setPilotReadiness] = useState<ReadinessReport | null>(
    null,
  );
  const [pilotReadinessError, setPilotReadinessError] = useState<string | null>(
    null,
  );
  const [transitionAction, setTransitionAction] = useState("");
  const [transitionNote, setTransitionNote] = useState("");
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [transitionSaving, setTransitionSaving] = useState(false);

  const [reviews, setReviews] = useState<RiskReviewCase[]>([]);
  const [reviewsError, setReviewsError] = useState<string | null>(null);
  const [reviewFilter, setReviewFilter] = useState("ALL");
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [reviewDetail, setReviewDetail] = useState<RiskReviewCase | null>(null);
  const [reviewAction, setReviewAction] = useState("IN_REVIEW");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewEvidence, setReviewEvidence] = useState("");
  const [reviewActionError, setReviewActionError] = useState<string | null>(
    null,
  );
  const [reviewSaving, setReviewSaving] = useState(false);

  const [candidates, setCandidates] = useState<CorrelationCandidate[]>([]);
  const [correlationError, setCorrelationError] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  const [metrics, setMetrics] = useState<CorrelationMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [correlationDecision, setCorrelationDecision] = useState("DUPLICATE");
  const [correlationExplanation, setCorrelationExplanation] = useState("");
  const [correlationSaveError, setCorrelationSaveError] = useState<
    string | null
  >(null);
  const [correlationSaving, setCorrelationSaving] = useState(false);

  const [sources, setSources] = useState<InfrastructureSource[]>([]);
  const [coverage, setCoverage] = useState<InfrastructureCoverage | null>(null);
  const [infrastructureError, setInfrastructureError] = useState<string | null>(
    null,
  );
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [sourceDetail, setSourceDetail] = useState<InfrastructureSource | null>(
    null,
  );
  const [sourceStatus, setSourceStatus] = useState("VERIFIED");
  const [sourceNote, setSourceNote] = useState("");
  const [sourceSaveError, setSourceSaveError] = useState<string | null>(null);
  const [sourceSaving, setSourceSaving] = useState(false);

  const [simulation, setSimulation] = useState<SimulationAudit | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  const [runs, setRuns] = useState<TraceRunSummary[]>([]);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [trace, setTrace] = useState<RiskTrace | null>(null);
  const [traceError, setTraceError] = useState<string | null>(null);
  const [traceExporting, setTraceExporting] = useState(false);

  const loadReadiness = useCallback(async () => {
    try {
      const result = await getReadiness(apiRequest);
      setReadiness(result);
      setReadinessError(null);
    } catch (error) {
      setReadinessError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadPilots = useCallback(async () => {
    try {
      const result = await getPilots(apiRequest);
      setPilots(result.items.map(normalizePilot));
      setSelectedPilotId((current) => current ?? result.items[0]?.id ?? null);
      setPilotsError(null);
    } catch (error) {
      setPilotsError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadReviews = useCallback(async () => {
    try {
      const result = await getRiskReviews(apiRequest, { limit: 50 });
      setReviews(result.items);
      setSelectedReviewId((current) => current ?? result.items[0]?.id ?? null);
      setReviewsError(null);
    } catch (error) {
      setReviewsError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadCorrelation = useCallback(async () => {
    try {
      const result = await getCorrelationCandidates(apiRequest, { limit: 50 });
      setCandidates(result.items);
      setSelectedCandidateId(
        (current) => current ?? result.items[0]?.id ?? null,
      );
      setCorrelationError(null);
    } catch (error) {
      setCorrelationError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadInfrastructure = useCallback(async () => {
    try {
      const [sourceResult, coverageResult] = await Promise.all([
        getInfrastructureSources(apiRequest),
        getInfrastructureCoverage(apiRequest),
      ]);
      setSources(sourceResult.items);
      setCoverage(coverageResult);
      setSelectedSourceId(
        (current) => current ?? sourceResult.items[0]?.id ?? null,
      );
      setInfrastructureError(null);
    } catch (error) {
      setInfrastructureError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadSimulation = useCallback(async () => {
    try {
      setSimulation(await getSimulationAudit(apiRequest));
      setSimulationError(null);
    } catch (error) {
      setSimulationError(errorMessage(error));
    }
  }, [apiRequest]);

  const loadRuns = useCallback(async () => {
    try {
      const result = await getTraceRuns(apiRequest);
      setRuns(result.items);
      setSelectedRunId((current) => current ?? result.items[0]?.id ?? null);
      setRunsError(null);
    } catch (error) {
      setRunsError(errorMessage(error));
    }
  }, [apiRequest]);

  useEffect(() => {
    let active = true;
    getReadiness(apiRequest)
      .then((result) => {
        if (active) {
          setReadiness(result);
          setReadinessError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setReadinessError(errorMessage(error));
      });
    getPilots(apiRequest)
      .then((result) => {
        if (active) {
          setPilots(result.items.map(normalizePilot));
          setSelectedPilotId(
            (current) => current ?? result.items[0]?.id ?? null,
          );
          setPilotsError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setPilotsError(errorMessage(error));
      });
    getRiskReviews(apiRequest, { limit: 50 })
      .then((result) => {
        if (active) {
          setReviews(result.items);
          setSelectedReviewId(
            (current) => current ?? result.items[0]?.id ?? null,
          );
          setReviewsError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setReviewsError(errorMessage(error));
      });
    getCorrelationCandidates(apiRequest, { limit: 50 })
      .then((result) => {
        if (active) {
          setCandidates(result.items);
          setSelectedCandidateId(
            (current) => current ?? result.items[0]?.id ?? null,
          );
          setCorrelationError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setCorrelationError(errorMessage(error));
      });
    Promise.all([
      getInfrastructureSources(apiRequest),
      getInfrastructureCoverage(apiRequest),
    ])
      .then(([sourceResult, coverageResult]) => {
        if (active) {
          setSources(sourceResult.items);
          setCoverage(coverageResult);
          setSelectedSourceId(
            (current) => current ?? sourceResult.items[0]?.id ?? null,
          );
          setInfrastructureError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setInfrastructureError(errorMessage(error));
      });
    getSimulationAudit(apiRequest)
      .then((result) => {
        if (active) {
          setSimulation(result);
          setSimulationError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setSimulationError(errorMessage(error));
      });
    getTraceRuns(apiRequest)
      .then((result) => {
        if (active) {
          setRuns(result.items);
          setSelectedRunId(
            (current) => current ?? result.items[0]?.id ?? null,
          );
          setRunsError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setRunsError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [apiRequest]);

  const selectedPilot =
    pilotDetail?.id === selectedPilotId
      ? pilotDetail
      : pilots.find((pilot) => pilot.id === selectedPilotId) ?? null;
  const selectedReview =
    reviewDetail ??
    reviews.find((item) => item.id === selectedReviewId) ??
    null;
  const selectedCandidate =
    candidates.find((item) => item.id === selectedCandidateId) ?? null;
  const selectedSource =
    sourceDetail?.id === selectedSourceId
      ? sourceDetail
      : sources.find((item) => item.id === selectedSourceId) ?? null;

  useEffect(() => {
    if (!selectedPilotId) {
      return;
    }
    let active = true;
    void getPilot(apiRequest, selectedPilotId)
      .then((result) => {
        if (active) setPilotDetail(normalizePilot(result));
      })
      .catch((error: unknown) => {
        if (active) setPilotsError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedPilotId]);

  useEffect(() => {
    if (!selectedPilotId) {
      return;
    }
    let active = true;
    void getPilotReadiness(apiRequest, selectedPilotId)
      .then((result) => {
        if (active) {
          setPilotReadiness(result);
          setPilotReadinessError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setPilotReadiness(null);
          setPilotReadinessError(errorMessage(error));
        }
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedPilotId]);

  useEffect(() => {
    if (!selectedReviewId) {
      return;
    }
    let active = true;
    void getRiskReview(apiRequest, selectedReviewId)
      .then((result) => {
        if (active) {
          setReviewDetail(result);
          setReviewActionError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setReviewActionError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedReviewId]);

  useEffect(() => {
    if (!selectedCandidate) {
      return;
    }
    let active = true;
    void getCorrelationMetrics(apiRequest, selectedCandidate.universe_key)
      .then((result) => {
        if (active) {
          setMetrics(result);
          setMetricsError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setMetrics(null);
          setMetricsError(errorMessage(error));
        }
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedCandidate]);

  useEffect(() => {
    if (!selectedSourceId) {
      return;
    }
    let active = true;
    void getInfrastructureSource(apiRequest, selectedSourceId)
      .then((result) => {
        if (active) {
          setSourceDetail(result);
          setSourceSaveError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setSourceSaveError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedSourceId]);

  useEffect(() => {
    if (tab !== "traceability" || !selectedRunId) {
      return;
    }
    let active = true;
    void getRiskTrace(apiRequest, selectedRunId)
      .then((result) => {
        if (active) {
          setTrace(result);
          setTraceError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setTrace(null);
          setTraceError(errorMessage(error));
        }
      });
    return () => {
      active = false;
    };
  }, [apiRequest, selectedRunId, tab]);

  useEffect(() => {
    if (tab !== "traceability") {
      return;
    }
    let active = true;
    void getTraceRuns(apiRequest)
      .then((result) => {
        if (active) {
          setRuns(result.items);
          setRunsError(null);
        }
      })
      .catch((error: unknown) => {
        if (active) setRunsError(errorMessage(error));
      });
    return () => {
      active = false;
    };
  }, [apiRequest, tab]);

  const filteredReviews = useMemo(
    () =>
      reviewFilter === "ALL"
        ? reviews
        : reviews.filter((item) => item.status === reviewFilter),
    [reviews, reviewFilter],
  );

  const pendingReviews = reviews.filter(
    (item) =>
      item.status === "UNREVIEWED" || item.status === "IN_REVIEW",
  ).length;
  const reviewedCandidates = candidates.filter(
    (item) => item.review_state === "REVIEWED",
  ).length;
  const verifiedSources = sources.filter(
    (item) => item.validation_status === "VERIFIED",
  ).length;

  async function runTransition() {
    if (!selectedPilot || !transitionAction) return;
    setTransitionSaving(true);
    setTransitionError(null);
    try {
      await transitionPilot(
        apiRequest,
        selectedPilot.id,
        transitionAction,
        transitionNote.trim() || undefined,
      );
      setTransitionAction("");
      setTransitionNote("");
      await loadPilots();
      await loadReadiness();
      if (selectedPilotId) {
        try {
          setPilotDetail(await getPilot(apiRequest, selectedPilotId));
        } catch (error) {
          setTransitionError(errorMessage(error));
        }
        try {
          setPilotReadiness(
            await getPilotReadiness(apiRequest, selectedPilotId),
          );
        } catch (error) {
          setPilotReadinessError(errorMessage(error));
        }
      }
    } catch (error) {
      setTransitionError(errorMessage(error));
    } finally {
      setTransitionSaving(false);
    }
  }

  async function submitReviewDecision() {
    if (!selectedReview) return;
    setReviewSaving(true);
    setReviewActionError(null);
    try {
      const updated = await decideRiskReview(apiRequest, selectedReview.id, {
        status: reviewAction,
        note: reviewNote.trim(),
        requested_evidence:
          reviewAction === "NEEDS_MORE_DATA"
            ? reviewEvidence.trim() || reviewNote.trim()
            : null,
      });
      setReviewDetail(updated);
      setReviewNote("");
      setReviewEvidence("");
      await loadReviews();
      await loadReadiness();
    } catch (error) {
      setReviewActionError(errorMessage(error));
    } finally {
      setReviewSaving(false);
    }
  }

  async function submitCorrelationReview() {
    if (!selectedCandidate) return;
    setCorrelationSaving(true);
    setCorrelationSaveError(null);
    try {
      await reviewCorrelationCandidate(apiRequest, selectedCandidate.id, {
        decision: correlationDecision,
        explanation: correlationExplanation.trim(),
      });
      setCorrelationExplanation("");
      await loadCorrelation();
      if (selectedCandidate) {
        setMetrics(
          await getCorrelationMetrics(
            apiRequest,
            selectedCandidate.universe_key,
          ),
        );
      }
    } catch (error) {
      setCorrelationSaveError(errorMessage(error));
    } finally {
      setCorrelationSaving(false);
    }
  }

  async function submitSourceValidation() {
    if (!selectedSource) return;
    setSourceSaving(true);
    setSourceSaveError(null);
    try {
      await validateInfrastructureSource(apiRequest, selectedSource.id, {
        status: sourceStatus,
        note: sourceNote.trim(),
      });
      setSourceNote("");
      await loadInfrastructure();
      await loadReadiness();
      setSourceDetail(
        await getInfrastructureSource(apiRequest, selectedSource.id),
      );
    } catch (error) {
      setSourceSaveError(errorMessage(error));
    } finally {
      setSourceSaving(false);
    }
  }

  async function exportTrace() {
    if (!selectedRunId) return;
    setTraceExporting(true);
    setTraceError(null);
    try {
      const payload = await downloadRiskTrace(apiRequest, selectedRunId);
      downloadJson("risk-assessment-trace-" + selectedRunId + ".json", payload);
    } catch (error) {
      setTraceError(errorMessage(error));
    } finally {
      setTraceExporting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-emerald-300/80">
            Phase 11 · Evidence and governance workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">
            Controlled pilot readiness
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
            Human review, traceability, correlation evaluation, infrastructure
            metadata and readiness gates. Nothing on this page authorizes
            dispatch, public alerts, resource allocation or an authoritative
            hazard declaration.
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-right">
          <p className="text-[10px] uppercase tracking-wide text-slate-500">
            Signed in as
          </p>
          <p className="mt-1 text-xs font-medium text-slate-200">
            {profile?.full_name ?? "Staff member"}
          </p>
          <p className="text-[10px] uppercase tracking-wide text-slate-500">
            {profile?.role ?? "Authenticated"}
          </p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-1 rounded-2xl border border-white/10 bg-white/[0.03] p-1.5">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            aria-controls={"panel-" + item.key}
            onClick={() => setTab(item.key)}
            className={
              "rounded-xl px-3 py-2 text-left transition " +
              (tab === item.key
                ? "bg-emerald-400/15 text-emerald-100"
                : "text-slate-400 hover:bg-white/5 hover:text-white")
            }
          >
            <span className="block text-xs font-semibold">{item.label}</span>
            <span className="hidden text-[10px] text-slate-500 sm:block">
              {item.hint}
            </span>
          </button>
        ))}
      </div>

      <div className="mt-5">
        <Advice>
          A score of PASS or READY_FOR_CONTROLLED_PILOT is a derived gate
          result, not an operator authorization. Model activation, pilot
          activation, dispatch and alerting remain separate, explicit
          administrator actions. Predictions are never verified hazards.
        </Advice>
      </div>

      <section
        id={"panel-" + tab}
        role="tabpanel"
        aria-label={TABS.find((item) => item.key === tab)?.label}
        className="mt-6"
      >
        {tab === "overview" ? (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
              {[
                ["Pilots", pilots.length],
                ["Open reviews", pendingReviews],
                ["Reviewed pairs", reviewedCandidates],
                ["Verified sources", verifiedSources],
                ["Simulations", simulation?.summary.simulations ?? 0],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3"
                >
                  <p className="text-[10px] uppercase tracking-wide text-slate-500">
                    {label}
                  </p>
                  <p className="mt-1 text-xl font-semibold text-white">
                    {value}
                  </p>
                </div>
              ))}
            </div>
            {readinessError ? (
              <ErrorNotice message={readinessError} onRetry={loadReadiness} />
            ) : null}
            {readiness ? (
              <ReadinessScorecard
                report={readiness}
                onExport={() =>
                  downloadJson("phase10-readiness-scorecard.json", readiness)
                }
              />
            ) : readinessError ? null : (
              <LoadingBlock label="Assessing readiness gates from persisted evidence…" />
            )}
          </div>
        ) : null}

        {tab === "pilots" ? (
          <div className="grid gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  Pilot registry
                </h2>
                <span className="text-[10px] uppercase tracking-wide text-slate-500">
                  {pilots.length} record(s)
                </span>
              </div>
              {pilotsError ? (
                <ErrorNotice message={pilotsError} onRetry={loadPilots} />
              ) : null}
              {pilots.length === 0 && !pilotsError ? (
                <EmptyState
                  title="No pilots registered"
                  hint="A pilot is created in DRAFT by an administrator through the governance API. Creating a pilot does not approve or activate it."
                />
              ) : null}
              <div className="space-y-2">
                {pilots.map((pilot) => (
                  <button
                    type="button"
                    key={pilot.id}
                    onClick={() => setSelectedPilotId(pilot.id)}
                    className={
                      "w-full rounded-xl border px-4 py-3 text-left transition " +
                      (pilot.id === selectedPilotId
                        ? "border-emerald-400/30 bg-emerald-400/[0.07]"
                        : "border-white/10 bg-white/[0.02] hover:border-white/20")
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-semibold text-slate-100">
                        {pilot.name}
                      </span>
                      <StatusPill status={pilot.status} />
                    </div>
                    <p className="mt-1 truncate text-[10px] text-slate-500">
                      {pilot.pilot_key} · {pilot.region}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {pilot.mode} · {formatDate(pilot.start_date)} –{" "}
                      {formatDate(pilot.end_date)}
                    </p>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-4">
              {selectedPilot ? (
                <>
                  <Card
                    title={selectedPilot.name}
                    eyebrow={selectedPilot.pilot_key}
                    actions={<StatusPill status={selectedPilot.status} />}
                  >
                    <p className="text-xs leading-relaxed text-slate-400">
                      {selectedPilot.description ?? "No description recorded."}
                    </p>
                    <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <KeyValue
                        label="Mode"
                        value={
                          <span className="font-mono text-[11px]">
                            {selectedPilot.mode}
                          </span>
                        }
                      />
                      <KeyValue label="Region" value={selectedPilot.region} />
                      <KeyValue
                        label="Evaluation window"
                        value={
                          formatDate(selectedPilot.start_date) +
                          " – " +
                          formatDate(selectedPilot.end_date)
                        }
                      />
                      <KeyValue
                        label="Owner"
                        value={selectedPilot.owner_id ?? "Not recorded"}
                      />
                      <KeyValue
                        label="Reviewers"
                        value={String(selectedPilot.reviewer_count)}
                      />
                      <KeyValue
                        label="Last updated"
                        value={formatDate(selectedPilot.updated_at)}
                      />
                    </dl>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                          Eligible categories
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {selectedPilot.eligible_categories.length ? (
                            selectedPilot.eligible_categories.map((item) => (
                              <span
                                key={item}
                                className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300"
                              >
                                {humanStatus(item)}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-slate-500">
                              None recorded
                            </span>
                          )}
                        </div>
                      </div>
                      <div>
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                          Operational restrictions
                        </p>
                        <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] text-slate-400">
                          {selectedPilot.operational_restrictions.length ? (
                            selectedPilot.operational_restrictions.map(
                              (item) => <li key={item}>{item}</li>,
                            )
                          ) : (
                            <li>None recorded</li>
                          )}
                        </ul>
                      </div>
                    </div>
                    <div className="mt-4">
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">
                        Evaluation protocol
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-xs leading-relaxed text-slate-300">
                        {selectedPilot.evaluation_protocol}
                      </p>
                    </div>
                    <div className="mt-3">
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">
                        Evaluation criteria
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-4 text-[11px] text-slate-400">
                        {selectedPilot.evaluation_criteria.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <p className="mt-4 border-t border-white/5 pt-3 text-[10px] leading-relaxed text-slate-500">
                      {selectedPilot.disclaimer}
                    </p>
                  </Card>

                  {isAdmin && selectedPilot.allowed_actions.length > 0 ? (
                    <Card
                      title="Lifecycle action"
                      eyebrow="Server-validated transition"
                    >
                      <div className="grid gap-3 sm:grid-cols-[1fr_1.4fr_auto]">
                        <label className="text-[10px] uppercase tracking-wide text-slate-500">
                          Action
                          <select
                            value={transitionAction}
                            onChange={(event) =>
                              setTransitionAction(event.target.value)
                            }
                            className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                          >
                            <option value="">Select action</option>
                            {selectedPilot.allowed_actions
                              .filter((action) => action !== "CREATE")
                              .map((action) => (
                                <option key={action} value={action}>
                                  {TRANSITION_LABELS[action] ?? humanStatus(action)}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label className="text-[10px] uppercase tracking-wide text-slate-500">
                          Note / reason
                          <textarea
                            value={transitionNote}
                            onChange={(event) =>
                              setTransitionNote(event.target.value)
                            }
                            rows={2}
                            placeholder="Required for rejection or pause; recorded in the audit trail."
                            className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                          />
                        </label>
                        <button
                          type="button"
                          disabled={!transitionAction || transitionSaving}
                          onClick={() => void runTransition()}
                          className="self-end rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {transitionSaving ? "Applying…" : "Apply transition"}
                        </button>
                      </div>
                      {transitionError ? (
                        <div className="mt-3">
                          <ErrorNotice message={transitionError} />
                        </div>
                      ) : null}
                      <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
                        Approval requires a different administrator and an
                        assigned reviewer. Activation requires readiness gates
                        to pass and a different administrator from the approver.
                        A pilot never authorizes model activation by itself.
                      </p>
                    </Card>
                  ) : null}

                  <Card
                    title="Pilot-specific readiness"
                    eyebrow="Independent gate evaluation"
                  >
                    {pilotReadinessError ? (
                      <ErrorNotice message={pilotReadinessError} />
                    ) : null}
                    {pilotReadiness ? (
                      <ReadinessScorecard
                        report={pilotReadiness}
                        title="Readiness with pilot checks"
                      />
                    ) : pilotReadinessError ? null : (
                      <LoadingBlock label="Evaluating pilot-specific readiness checks…" />
                    )}
                  </Card>

                  <Card title="Audit history" eyebrow="Append-only transitions">
                    {selectedPilot.history.length ? (
                      <ol className="space-y-2">
                        {selectedPilot.history.map((event) => (
                          <li
                            key={event.id}
                            className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="text-xs font-medium text-slate-200">
                                {humanStatus(event.action)} ·{" "}
                                {event.from_status
                                  ? humanStatus(event.from_status) + " → "
                                  : ""}
                                {humanStatus(event.to_status)}
                              </span>
                              <span className="text-[10px] text-slate-500">
                                {formatDate(event.created_at)}
                              </span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-500">
                              {event.actor_email ?? "Unknown actor"}
                              {event.note ? " · " + event.note : ""}
                            </p>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <EmptyState
                        title="No transitions recorded"
                        hint="Every create and lifecycle action is written to the append-only transition table."
                      />
                    )}
                  </Card>
                </>
              ) : (
                <EmptyState
                  title="Select a pilot"
                  hint="Choose a pilot from the registry to inspect its scope, approval state and readiness gates."
                />
              )}
            </div>
          </div>
        ) : null}

        {tab === "reviews" ? (
          <div className="grid gap-5 lg:grid-cols-[24rem_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-white">
                  Human review queue
                </h2>
                <select
                  value={reviewFilter}
                  onChange={(event) => setReviewFilter(event.target.value)}
                  aria-label="Filter reviews by status"
                  className="rounded-lg border border-white/10 bg-slate-950 px-2 py-1.5 text-[11px] text-slate-300"
                >
                  <option value="ALL">All statuses</option>
                  <option value="UNREVIEWED">Unreviewed</option>
                  <option value="IN_REVIEW">In review</option>
                  <option value="ACCEPTED">Accepted</option>
                  <option value="REJECTED">Rejected</option>
                  <option value="NEEDS_INVESTIGATION">Needs investigation</option>
                  <option value="NEEDS_MORE_DATA">Needs more data</option>
                </select>
              </div>
              {reviewsError ? (
                <ErrorNotice message={reviewsError} onRetry={loadReviews} />
              ) : null}
              {filteredReviews.length === 0 && !reviewsError ? (
                <EmptyState
                  title="No review cases match"
                  hint="Review cases are opened by staff against a persisted risk assessment cell. Opening a case does not verify a hazard and does not change the score."
                />
              ) : null}
              <div className="space-y-2">
                {filteredReviews.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => {
                      setSelectedReviewId(item.id);
                      setReviewDetail(null);
                      setReviewActionError(null);
                    }}
                    className={
                      "w-full rounded-xl border px-4 py-3 text-left transition " +
                      (item.id === selectedReviewId
                        ? "border-emerald-400/30 bg-emerald-400/[0.07]"
                        : "border-white/10 bg-white/[0.02] hover:border-white/20")
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[11px] text-slate-200">
                        {item.risk?.h3_cell_id ?? item.cell_id}
                      </span>
                      <StatusPill status={item.status} />
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {item.risk?.risk_category ?? "Uncategorised"} · score{" "}
                      {formatNumber(item.risk?.risk_score ?? null)}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {item.pilot?.name ?? "No pilot context"} ·{" "}
                      {formatDate(item.created_at)}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {selectedReview ? (
                <>
                  <Card
                    title={
                      "Cell " +
                      (selectedReview.risk?.h3_cell_id ?? selectedReview.cell_id)
                    }
                    eyebrow="Human-in-the-loop risk review"
                    actions={<StatusPill status={selectedReview.status} />}
                  >
                    <p className="text-xs leading-relaxed text-slate-400">
                      {selectedReview.review_disclaimer}
                    </p>
                    <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <KeyValue
                        label="Model prediction"
                        value={
                          <span className="text-lg font-semibold text-white">
                            {formatNumber(selectedReview.risk?.risk_score ?? null)}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Model band"
                        value={selectedReview.risk?.risk_category ?? "Unknown"}
                      />
                      <KeyValue
                        label="Confidence"
                        value={formatNumber(
                          selectedReview.risk?.confidence ?? null,
                        )}
                      />
                      <KeyValue
                        label="Calculated"
                        value={formatDate(selectedReview.risk?.calculated_at)}
                      />
                      <KeyValue
                        label="Model version"
                        value={
                          selectedReview.run?.model_version ??
                          selectedReview.risk?.model_version ??
                          "Unknown"
                        }
                      />
                      <KeyValue
                        label="Config hash"
                        value={
                          <span className="break-all font-mono text-[10px]">
                            {selectedReview.run?.config_hash ??
                              selectedReview.risk?.config_hash ??
                              "Unknown"}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Spatial unit"
                        value={
                          <span className="font-mono text-[10px]">
                            {selectedReview.risk?.h3_cell_id ?? "Unknown"} · res{" "}
                            {selectedReview.run?.resolution ?? "?"}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Time window"
                        value={
                          formatDate(selectedReview.run?.window_start) +
                          " – " +
                          formatDate(selectedReview.run?.window_end)
                        }
                      />
                      <KeyValue
                        label="Pilot"
                        value={selectedReview.pilot?.name ?? "No pilot context"}
                      />
                      <KeyValue
                        label="Assigned reviewer"
                        value={selectedReview.assigned_reviewer_id ?? "Unassigned"}
                      />
                      <KeyValue
                        label="Source incidents"
                        value={String(selectedReview.run?.incident_count ?? "Unknown")}
                      />
                      <KeyValue
                        label="Population cells"
                        value={String(selectedReview.run?.cell_count ?? "Unknown")}
                      />
                    </dl>
                  </Card>

                  <Card
                    title="Factor evidence"
                    eyebrow="Persisted assessment inputs"
                  >
                    {selectedReview.risk?.factor_contributions.length ? (
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[34rem] text-left text-xs">
                          <thead className="text-[10px] uppercase tracking-wide text-slate-500">
                            <tr>
                              <th className="py-1 pr-3">Factor</th>
                              <th className="py-1 pr-3">Contribution</th>
                              <th className="py-1">Explanation</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {selectedReview.risk.factor_contributions.map(
                              (factor, index) => (
                                <tr key={String(factor.key ?? index)}>
                                  <td className="py-2 pr-3 text-slate-200">
                                    {String(
                                      factor.label ??
                                        factor.key ??
                                        "Factor " + (index + 1),
                                    )}
                                  </td>
                                  <td className="py-2 pr-3 font-mono text-[11px] text-slate-300">
                                    {factor.contribution === null ||
                                    factor.contribution === undefined
                                      ? "Unknown"
                                      : formatNumber(Number(factor.contribution), 4)}
                                  </td>
                                  <td className="py-2 text-[11px] leading-relaxed text-slate-400">
                                    {factor.explanation
                                      ? String(factor.explanation)
                                      : "No explanation recorded."}
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <EmptyState
                        title="No factor contributions recorded"
                        hint="The assessment is still reviewable, but missing factor provenance must remain explicit rather than inferred."
                      />
                    )}
                    <div className="mt-3 rounded-lg border border-white/5 bg-slate-950/40 p-3">
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">
                        Available factors snapshot
                      </p>
                      <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all text-[10px] text-slate-400">
                        {JSON.stringify(
                          selectedReview.risk?.available_factors ?? [],
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </Card>

                  <Card
                    title="Record a review decision"
                    eyebrow="Server-enforced identity and transition"
                  >
                    <p className="text-[11px] leading-relaxed text-slate-400">
                      {selectedReview.prediction_vs_review} A note is required
                      for every decision. Requesting data must record what
                      evidence is missing.
                    </p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
                      <label className="text-[10px] uppercase tracking-wide text-slate-500">
                        Decision
                        <select
                          value={reviewAction}
                          onChange={(event) => setReviewAction(event.target.value)}
                          className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                        >
                          {REVIEW_ACTIONS.map((option) => (
                            <option key={option.status} value={option.status}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="self-end text-[10px] text-slate-500">
                        {selectedReview.status === "UNREVIEWED"
                          ? "Start the review before a final decision."
                          : "Allowed transitions are validated on the server."}
                      </div>
                    </div>
                    <label className="mt-3 block text-[10px] uppercase tracking-wide text-slate-500">
                      Review note (required)
                      <textarea
                        value={reviewNote}
                        onChange={(event) => setReviewNote(event.target.value)}
                        rows={3}
                        placeholder="Describe what you inspected and why this decision is appropriate."
                        className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                      />
                    </label>
                    {reviewAction === "NEEDS_MORE_DATA" ? (
                      <label className="mt-3 block text-[10px] uppercase tracking-wide text-slate-500">
                        Requested evidence
                        <textarea
                          value={reviewEvidence}
                          onChange={(event) =>
                            setReviewEvidence(event.target.value)
                          }
                          rows={2}
                          placeholder="Name the dataset, field, date range or authority needed."
                          className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                        />
                      </label>
                    ) : null}
                    {reviewActionError ? (
                      <div className="mt-3">
                        <ErrorNotice message={reviewActionError} />
                      </div>
                    ) : null}
                    <button
                      type="button"
                      disabled={reviewSaving}
                      onClick={() => void submitReviewDecision()}
                      className="mt-3 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {reviewSaving ? "Recording…" : "Record decision"}
                    </button>
                  </Card>

                  <Card title="Review history" eyebrow="Append-only audit">
                    {selectedReview.events.length ? (
                      <ol className="space-y-2">
                        {selectedReview.events.map((event) => (
                          <li
                            key={event.id}
                            className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="text-xs font-medium text-slate-200">
                                {event.from_status
                                  ? humanStatus(event.from_status) + " → "
                                  : ""}
                                {humanStatus(event.to_status)}
                              </span>
                              <span className="text-[10px] text-slate-500">
                                {formatDate(event.created_at)}
                              </span>
                            </div>
                            <p className="mt-1 text-[10px] text-slate-500">
                              {event.actor_email ?? "Unknown reviewer"}
                              {event.note ? " · " + event.note : ""}
                            </p>
                            {event.requested_evidence ? (
                              <p className="mt-1 text-[10px] text-amber-200/80">
                                Evidence requested: {event.requested_evidence}
                              </p>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <EmptyState
                        title="No review events"
                        hint="Every decision is timestamped and tied to the authenticated reviewer."
                      />
                    )}
                  </Card>
                </>
              ) : (
                <EmptyState
                  title="Select a review case"
                  hint="Inspect the persisted assessment, factor evidence and prior human decisions before recording a review."
                />
              )}
            </div>
          </div>
        ) : null}

        {tab === "correlation" ? (
          <div className="space-y-5">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                  Candidate pairs
                </p>
                <p className="mt-1 text-2xl font-semibold text-white">
                  {candidates.length}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                  Pairs with a reviewer label
                </p>
                <p className="mt-1 text-2xl font-semibold text-white">
                  {reviewedCandidates}
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                  Evidence kind
                </p>
                <p className="mt-1 text-xs font-medium text-slate-200">
                  Reviewer sample judgments
                </p>
                <p className="mt-1 text-[10px] text-slate-500">
                  Never presented as complete ground truth.
                </p>
              </div>
            </div>

            <div className="grid gap-5 lg:grid-cols-[24rem_minmax(0,1fr)]">
              <div className="space-y-3">
                <h2 className="text-sm font-semibold text-white">
                  Correlation candidates
                </h2>
                {correlationError ? (
                  <ErrorNotice
                    message={correlationError}
                    onRetry={loadCorrelation}
                  />
                ) : null}
                {candidates.length === 0 && !correlationError ? (
                  <EmptyState
                    title="No correlation candidates"
                    hint="Candidate pairs are generated from persisted incident relationships. Creating candidates does not assert that two incidents are duplicates."
                  />
                ) : null}
                <div className="space-y-2">
                  {candidates.map((candidate) => (
                    <button
                      type="button"
                      key={candidate.id}
                      onClick={() => {
                        setSelectedCandidateId(candidate.id);
                        setCorrelationSaveError(null);
                      }}
                      className={
                        "w-full rounded-xl border px-4 py-3 text-left transition " +
                        (candidate.id === selectedCandidateId
                          ? "border-emerald-400/30 bg-emerald-400/[0.07]"
                          : "border-white/10 bg-white/[0.02] hover:border-white/20")
                      }
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[10px] text-slate-200">
                          {candidate.candidate_key}
                        </span>
                        <StatusPill status={candidate.review_state} />
                      </div>
                      <p className="mt-1 text-[10px] text-slate-500">
                        Similarity{" "}
                        {formatNumber(candidate.similarity_score)} ·{" "}
                        {candidate.method}@{candidate.method_version}
                      </p>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {candidate.universe_key} ·{" "}
                        {formatDate(candidate.generated_at)}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                {selectedCandidate ? (
                  <>
                    <Card
                      title="Candidate pair"
                      eyebrow="Generated suggestion, not a finding"
                      actions={
                        <StatusPill status={selectedCandidate.review_state} />
                      }
                    >
                      <div className="grid gap-3 sm:grid-cols-2">
                        {[
                          ["Source incident", selectedCandidate.source_incident],
                          ["Target incident", selectedCandidate.target_incident],
                        ].map(([label, incident]) => {
                          const brief = incident as CorrelationCandidate["source_incident"];
                          return (
                            <div
                              key={String(label)}
                              className="rounded-lg border border-white/5 bg-slate-950/40 p-3"
                            >
                              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                {String(label)}
                              </p>
                              <p className="mt-1 text-xs font-medium text-slate-200">
                                {brief?.title ?? "Incident unavailable"}
                              </p>
                              <p className="mt-1 text-[10px] text-slate-500">
                                {brief
                                  ? [
                                      brief.id,
                                      brief.category ?? "Uncategorised",
                                      formatDate(brief.created_at),
                                    ].join(" · ")
                                  : "No incident provenance returned."}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                      <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <KeyValue
                          label="Similarity"
                          value={formatNumber(
                            selectedCandidate.similarity_score,
                          )}
                        />
                        <KeyValue
                          label="Method"
                          value={
                            selectedCandidate.method +
                            "@" +
                            selectedCandidate.method_version
                          }
                        />
                        <KeyValue
                          label="Generated"
                          value={formatDate(selectedCandidate.generated_at)}
                        />
                        <KeyValue
                          label="Universe"
                          value={selectedCandidate.universe_key}
                        />
                        <KeyValue
                          label="Reference universe complete"
                          value={
                            selectedCandidate.universe_reference_complete
                              ? "Yes"
                              : "No"
                          }
                        />
                        <KeyValue
                          label="Reference size"
                          value={
                            selectedCandidate.reference_universe_size ??
                            "Unknown"
                          }
                        />
                        <KeyValue
                          label="Reference note"
                          value={
                            selectedCandidate.reference_note ??
                            "No note recorded"
                          }
                        />
                        <KeyValue
                          label="Synthetic fixture"
                          value={
                            selectedCandidate.synthetic_fixture === null
                              ? "Unknown"
                              : selectedCandidate.synthetic_fixture
                                ? "Yes"
                                : "No"
                          }
                        />
                        <KeyValue
                          label="Reviewers"
                          value={String(selectedCandidate.reviews.length)}
                        />
                      </dl>
                      <p className="mt-4 border-t border-white/5 pt-3 text-[10px] leading-relaxed text-slate-500">
                        {selectedCandidate.disclaimer}
                      </p>
                    </Card>

                    <Card
                      title="Reviewer labels for this pair"
                      eyebrow="Independent judgments"
                    >
                      {selectedCandidate.reviews.length ? (
                        <ul className="space-y-2">
                          {selectedCandidate.reviews.map((review) => (
                            <li
                              key={review.id}
                              className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <StatusPill status={review.decision} />
                                <span className="text-[10px] text-slate-500">
                                  {formatDate(review.created_at)}
                                </span>
                              </div>
                              <p className="mt-1 text-[11px] text-slate-400">
                                {review.explanation ??
                                  review.note ??
                                  "No explanation recorded."}
                              </p>
                              <p className="mt-1 text-[10px] text-slate-600">
                                {review.reviewer_email ?? review.reviewer_id}
                              </p>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <EmptyState
                          title="No reviewer labels yet"
                          hint="A label records a reviewer's judgment about this pair. It does not create a confirmed duplicate or a validated hazard."
                        />
                      )}
                    </Card>

                    <Card title="Record an independent label" eyebrow="One label per reviewer">
                      <div className="grid gap-3 sm:grid-cols-[1fr_1.5fr_auto]">
                        <label className="text-[10px] uppercase tracking-wide text-slate-500">
                          Decision
                          <select
                            value={correlationDecision}
                            onChange={(event) =>
                              setCorrelationDecision(event.target.value)
                            }
                            className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                          >
                            <option value="DUPLICATE">Duplicate</option>
                            <option value="NOT_DUPLICATE">Not duplicate</option>
                            <option value="INSUFFICIENT_EVIDENCE">
                              Insufficient evidence
                            </option>
                          </select>
                        </label>
                        <label className="text-[10px] uppercase tracking-wide text-slate-500">
                          Explanation (required)
                          <textarea
                            value={correlationExplanation}
                            onChange={(event) =>
                              setCorrelationExplanation(event.target.value)
                            }
                            rows={2}
                            placeholder="Explain the comparison and any ambiguity."
                            className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                          />
                        </label>
                        <button
                          type="button"
                          disabled={
                            correlationSaving ||
                            correlationExplanation.trim().length < 10
                          }
                          onClick={() => void submitCorrelationReview()}
                          className="self-end rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {correlationSaving ? "Recording…" : "Record label"}
                        </button>
                      </div>
                      {correlationSaveError ? (
                        <div className="mt-3">
                          <ErrorNotice message={correlationSaveError} />
                        </div>
                      ) : null}
                    </Card>

                    <Card
                      title={"Evaluation metrics · " + selectedCandidate.universe_key}
                      eyebrow="Computed only from recorded labels"
                    >
                      {metricsError ? (
                        <ErrorNotice message={metricsError} />
                      ) : null}
                      {metrics ? (
                        <div className="space-y-4">
                          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                            {[
                              ["Precision", metrics.metrics.precision],
                              ["Recall", metrics.metrics.recall],
                              ["F1", metrics.metrics.f1],
                              [
                                "Reviewed",
                                metrics.reviewed_candidates,
                              ],
                            ].map(([label, value]) => (
                              <div
                                key={String(label)}
                                className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                              >
                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                  {label}
                                </p>
                                <p className="mt-1 text-base font-semibold text-white">
                                  {typeof value === "number"
                                    ? formatNumber(value)
                                    : value ?? "Unknown"}
                                </p>
                              </div>
                            ))}
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className="rounded-lg border border-white/5 bg-slate-950/40 p-3">
                              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                Confusion matrix
                              </p>
                              <dl className="mt-2 grid grid-cols-2 gap-2 text-xs">
                                <KeyValue
                                  label="True positive"
                                  value={metrics.confusion_matrix.true_positive}
                                />
                                <KeyValue
                                  label="False positive"
                                  value={metrics.confusion_matrix.false_positive}
                                />
                                <KeyValue
                                  label="False negative"
                                  value={
                                    metrics.confusion_matrix.false_negative ??
                                    "Unknown"
                                  }
                                />
                                <KeyValue
                                  label="True negative"
                                  value={
                                    metrics.confusion_matrix.true_negative ??
                                    "Unknown"
                                  }
                                />
                              </dl>
                            </div>
                            <div className="rounded-lg border border-white/5 bg-slate-950/40 p-3">
                              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                Reviewer agreement
                              </p>
                              <dl className="mt-2 space-y-2 text-xs">
                                <KeyValue
                                  label="Pairwise agreement"
                                  value={
                                    metrics.reviewer_agreement
                                      .pairwise_agreement === null
                                      ? "Not estimable"
                                      : formatNumber(
                                          metrics.reviewer_agreement
                                            .pairwise_agreement,
                                        )
                                  }
                                />
                                <KeyValue
                                  label="Distinct reviewers"
                                  value={
                                    metrics.reviewer_agreement
                                      .distinct_reviewers
                                  }
                                />
                                <KeyValue
                                  label="Compared reviewer pairs"
                                  value={
                                    metrics.reviewer_agreement
                                      .compared_reviewer_pairs
                                  }
                                />
                              </dl>
                            </div>
                          </div>
                          <div className="rounded-lg border border-amber-400/20 bg-amber-400/[0.04] p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                              Metric limits
                            </p>
                            <p className="mt-1 text-[11px] text-amber-100/80">
                              {metrics.reference.recall_reason}
                            </p>
                            <p className="mt-1 text-[10px] text-slate-500">
                              Evidence kind: {metrics.evidence_kind} · synthetic
                              provenance:{" "}
                              {metrics.synthetic_provenance.toLowerCase()} ·
                              validated ground truth:{" "}
                              {metrics.is_validated_ground_truth ? "yes" : "no"}
                            </p>
                            <ul className="mt-2 list-disc space-y-1 pl-4 text-[10px] text-amber-100/70">
                              {metrics.limitations.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <button
                            type="button"
                            onClick={() =>
                              downloadJson(
                                "correlation-metrics-" +
                                  selectedCandidate.universe_key +
                                  ".json",
                                metrics,
                              )
                            }
                            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 transition hover:border-white/20"
                          >
                            Export metrics JSON
                          </button>
                        </div>
                      ) : metricsError ? null : (
                        <LoadingBlock label="Computing reviewer-labelled metrics…" />
                      )}
                    </Card>
                  </>
                ) : (
                  <EmptyState
                    title="Select a candidate pair"
                    hint="Review the two incidents, their similarity method and the available reference universe before recording a decision."
                  />
                )}
              </div>
            </div>
          </div>
        ) : null}

        {tab === "traceability" ? (
          <div className="grid gap-5 lg:grid-cols-[23rem_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">
                  Risk assessments
                </h2>
                <span className="text-[10px] uppercase tracking-wide text-slate-500">
                  {runs.length} run(s)
                </span>
              </div>
              {runsError ? (
                <ErrorNotice message={runsError} onRetry={loadRuns} />
              ) : null}
              {runs.length === 0 && !runsError ? (
                <EmptyState
                  title="No risk assessments"
                  hint="Run a persisted risk assessment first; traceability only reads existing runs, cells, models and reviews."
                />
              ) : null}
              <div className="space-y-2">
                {runs.map((run) => (
                  <button
                    type="button"
                    key={run.id}
                    onClick={() => setSelectedRunId(run.id)}
                    className={
                      "w-full rounded-xl border px-4 py-3 text-left transition " +
                      (run.id === selectedRunId
                        ? "border-emerald-400/30 bg-emerald-400/[0.07]"
                        : "border-white/10 bg-white/[0.02] hover:border-white/20")
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px] text-slate-200">
                        {run.id.slice(0, 8)}…
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {run.cell_count} cells
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {run.model_version} · res {run.resolution} ·{" "}
                      {run.window_hours}h
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {formatDate(run.calculated_at)} · {run.review_cases} review
                      case(s)
                    </p>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {traceError ? (
                <ErrorNotice message={traceError} onRetry={() => {
                  if (selectedRunId) {
                    setTraceError(null);
                    void getRiskTrace(apiRequest, selectedRunId)
                      .then(setTrace)
                      .catch((error: unknown) =>
                        setTraceError(errorMessage(error)),
                      );
                  }
                }} />
              ) : null}
              {trace ? (
                <>
                  <Card
                    title="Assessment trace"
                    eyebrow="Read-only provenance"
                    actions={
                      <button
                        type="button"
                        disabled={traceExporting}
                        onClick={() => void exportTrace()}
                        className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 transition hover:border-white/20 disabled:opacity-40"
                      >
                        {traceExporting ? "Exporting…" : "Export trace JSON"}
                      </button>
                    }
                  >
                    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <KeyValue
                        label="Run"
                        value={
                          <span className="break-all font-mono text-[10px]">
                            {trace.assessment.id}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Model"
                        value={trace.assessment.model_version}
                      />
                      <KeyValue
                        label="Config hash"
                        value={
                          <span className="break-all font-mono text-[10px]">
                            {trace.assessment.config_hash}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Generated"
                        value={formatDate(trace.assessment.calculated_at)}
                      />
                      <KeyValue
                        label="Spatial resolution"
                        value={"H3 res " + trace.assessment.resolution}
                      />
                      <KeyValue
                        label="Time window"
                        value={
                          formatDate(trace.assessment.window_start) +
                          " – " +
                          formatDate(trace.assessment.window_end)
                        }
                      />
                      <KeyValue
                        label="Incidents"
                        value={trace.assessment.incident_count}
                      />
                      <KeyValue
                        label="Cells"
                        value={trace.assessment.cell_count}
                      />
                    </dl>
                    <div
                      className={
                        "mt-4 rounded-xl border px-3 py-2 text-[11px] " +
                        (trace.provenance.complete
                          ? "border-emerald-400/20 bg-emerald-400/[0.04] text-emerald-100/80"
                          : "border-amber-400/20 bg-amber-400/[0.04] text-amber-100/80")
                      }
                    >
                      <p className="font-semibold">
                        Provenance{" "}
                        {trace.provenance.complete ? "complete" : "incomplete"}
                      </p>
                      {trace.provenance.missing.length ? (
                        <ul className="mt-1 list-disc space-y-1 pl-4">
                          {trace.provenance.missing.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-1">
                          Model configuration, input lineage and reviews are
                          linked.
                        </p>
                      )}
                    </div>
                  </Card>

                  <Card title="Model configuration" eyebrow="Registry linkage">
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <KeyValue
                        label="Registry entry found"
                        value={trace.model_configuration.found ? "Yes" : "No"}
                      />
                      <KeyValue
                        label="Config hash matches"
                        value={
                          trace.model_configuration.config_hash_matches === null
                            ? "Unknown"
                            : trace.model_configuration.config_hash_matches
                              ? "Yes"
                              : "No"
                        }
                      />
                      <KeyValue
                        label="Registered version"
                        value={trace.model_configuration.version}
                      />
                      <KeyValue
                        label="Active version at export"
                        value={
                          trace.model_configuration.active_version ?? "Unknown"
                        }
                      />
                      <KeyValue
                        label="Activation changed"
                        value="No"
                      />
                      <KeyValue
                        label="Registered"
                        value={formatDate(
                          trace.model_configuration.registered_at,
                        )}
                      />
                    </dl>
                    <p className="mt-3 text-[11px] leading-relaxed text-slate-400">
                      {trace.model_configuration.note}
                    </p>
                    {trace.model_configuration.config ? (
                      <pre className="mt-3 max-h-64 overflow-auto rounded-lg border border-white/5 bg-slate-950/50 p-3 text-[10px] text-slate-400">
                        {JSON.stringify(
                          trace.model_configuration.config,
                          null,
                          2,
                        )}
                      </pre>
                    ) : null}
                  </Card>

                  <Card title="Inputs and lineage" eyebrow="What the score used">
                    <dl className="grid gap-3 sm:grid-cols-2">
                      <KeyValue
                        label="Incidents in window"
                        value={trace.inputs.incident_count}
                      />
                      <KeyValue
                        label="Cells scored"
                        value={trace.inputs.cell_count}
                      />
                      <KeyValue
                        label="Query parameters"
                        value={
                          <span className="break-all font-mono text-[10px]">
                            {JSON.stringify(trace.inputs.query_parameters)}
                          </span>
                        }
                      />
                      <KeyValue
                        label="Source datasets"
                        value={
                          trace.inputs.source_datasets.length
                            ? trace.inputs.source_datasets.join(", ")
                            : "No dataset lineage recorded"
                        }
                      />
                    </dl>
                    <p className="mt-3 text-[10px] text-slate-500">
                      Source lineage complete:{" "}
                      {trace.inputs.source_lineage_complete ? "yes" : "no"}.
                      Missing lineage is shown explicitly and is never inferred.
                    </p>
                  </Card>

                  <Card
                    title="Factor contributions"
                    eyebrow="Aggregated over returned cells"
                  >
                    {trace.factor_contributions.length ? (
                      <div className="overflow-x-auto">
                        <table className="w-full min-w-[38rem] text-left text-xs">
                          <thead className="text-[10px] uppercase tracking-wide text-slate-500">
                            <tr>
                              <th className="py-1 pr-3">Factor</th>
                              <th className="py-1 pr-3">Availability</th>
                              <th className="py-1 pr-3">Mean</th>
                              <th className="py-1 pr-3">Range</th>
                              <th className="py-1">Last explanation</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {trace.factor_contributions.map((factor) => (
                              <tr key={factor.key}>
                                <td className="py-2 pr-3 text-slate-200">
                                  {factor.label}
                                </td>
                                <td className="py-2 pr-3 text-slate-400">
                                  {factor.available_share === null
                                    ? "Unknown"
                                    : formatNumber(
                                        factor.available_share * 100,
                                        1,
                                      ) + "%"}
                                </td>
                                <td className="py-2 pr-3 font-mono text-[11px] text-slate-300">
                                  {formatNumber(factor.mean_contribution, 4)}
                                </td>
                                <td className="py-2 pr-3 font-mono text-[10px] text-slate-500">
                                  {formatNumber(factor.contribution_min, 4)} –{" "}
                                  {formatNumber(factor.contribution_max, 4)}
                                </td>
                                <td className="py-2 text-[11px] text-slate-400">
                                  {factor.last_explanation ??
                                    "No explanation recorded."}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <EmptyState
                        title="No factor contributions"
                        hint="Missing factor provenance remains explicit; the trace does not reconstruct contributions."
                      />
                    )}
                  </Card>

                  <Card
                    title="Spatial units"
                    eyebrow={
                      trace.spatial_units.truncated
                        ? "Truncated view"
                        : "Returned cells"
                    }
                  >
                    <p className="text-[11px] text-slate-500">
                      {trace.spatial_units.returned_cells} of{" "}
                      {trace.spatial_units.total_cells} cells returned at H3
                      resolution {trace.spatial_units.resolution}.
                    </p>
                    <div className="mt-2 max-h-72 overflow-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="sticky top-0 bg-slate-950 text-[10px] uppercase tracking-wide text-slate-500">
                          <tr>
                            <th className="py-1 pr-3">H3 cell</th>
                            <th className="py-1 pr-3">Score</th>
                            <th className="py-1 pr-3">Band</th>
                            <th className="py-1">Calculated</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          {trace.spatial_units.cells.map((cell) => (
                            <tr key={cell.id}>
                              <td className="py-1.5 pr-3 font-mono text-[10px] text-slate-300">
                                {cell.h3_cell_id}
                              </td>
                              <td className="py-1.5 pr-3 text-slate-300">
                                {formatNumber(cell.risk_score)}
                              </td>
                              <td className="py-1.5 pr-3 text-slate-400">
                                {cell.risk_category}
                              </td>
                              <td className="py-1.5 text-[10px] text-slate-500">
                                {formatDate(cell.calculated_at)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>

                  <Card title="Reviews and pilot context" eyebrow="Human layer">
                    <dl className="grid gap-3 sm:grid-cols-3">
                      <KeyValue
                        label="Review cases"
                        value={trace.reviews.case_count}
                      />
                      <KeyValue
                        label="Status counts"
                        value={
                          Object.keys(trace.reviews.status_counts).length
                            ? Object.entries(trace.reviews.status_counts)
                                .map(
                                  ([key, value]) =>
                                    humanStatus(key) + ": " + value,
                                )
                                .join(" · ")
                            : "No reviews"
                        }
                      />
                      <KeyValue
                        label="Reviewers"
                        value={
                          trace.reviews.reviewers.length
                            ? trace.reviews.reviewers.join(", ")
                            : "None"
                        }
                      />
                    </dl>
                    <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
                      {trace.reviews.note}
                    </p>
                    <ul className="mt-3 space-y-2">
                      {trace.reviews.cases.map((item) => (
                        <li
                          key={item.id}
                          className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-mono text-[10px] text-slate-300">
                              {item.cell_id}
                            </span>
                            <StatusPill status={item.status} />
                          </div>
                          <p className="mt-1 text-[10px] text-slate-500">
                            {item.pilot
                              ? item.pilot.name +
                                " · " +
                                humanStatus(item.pilot.status)
                              : "No pilot context"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </Card>

                  <Card title="Trace limitations" eyebrow="Explicit boundaries">
                    <ul className="list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-400">
                      {trace.limitations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </Card>
                </>
              ) : traceError ? null : selectedRunId ? (
                <LoadingBlock label="Building assessment trace…" />
              ) : (
                <EmptyState
                  title="Select an assessment"
                  hint="A trace links a persisted risk assessment to its model version, inputs, factors, spatial cells, reviews and pilot context."
                />
              )}
            </div>
          </div>
        ) : null}

        {tab === "infrastructure" ? (
          <div className="space-y-5">
            <Advice>
              This registry stores source metadata only. No road, bridge,
              facility, water, drainage, emergency or transit asset data is
              fetched, ingested or implied to exist. VERIFIED means the
              metadata passed completeness checks, not that the dataset is
              complete or current.
            </Advice>
            {infrastructureError ? (
              <ErrorNotice
                message={infrastructureError}
                onRetry={loadInfrastructure}
              />
            ) : null}
            {coverage ? (
              <>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                  {coverage.domains.map((domain) => (
                    <div
                      key={domain.category}
                      className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3"
                    >
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">
                        {domain.label}
                      </p>
                      <p className="mt-1 text-xs font-medium text-slate-200">
                        {humanStatus(domain.state)}
                      </p>
                      <p className="mt-1 text-[10px] text-slate-500">
                        {domain.verified}/{domain.sources} verified
                      </p>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-slate-500">
                  {coverage.verified_domains} of {coverage.total_domains}{" "}
                  domains have verified metadata · asset data available:{" "}
                  {coverage.asset_data_available ? "yes" : "no"}.
                </p>
              </>
            ) : infrastructureError ? null : (
              <LoadingBlock label="Loading infrastructure coverage…" />
            )}

            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
              <Card title="Source registry" eyebrow="Metadata and validation">
                {sources.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[54rem] text-left text-xs">
                      <thead className="text-[10px] uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="py-1 pr-3">Source</th>
                          <th className="py-1 pr-3">Domain</th>
                          <th className="py-1 pr-3">Provider</th>
                          <th className="py-1 pr-3">Status</th>
                          <th className="py-1 pr-3">Retrieved</th>
                          <th className="py-1">SHA-256</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {sources.map((source) => (
                          <tr
                            key={source.id}
                            onClick={() => setSelectedSourceId(source.id)}
                            className={
                              "cursor-pointer transition hover:bg-white/[0.03] " +
                              (source.id === selectedSourceId
                                ? "bg-emerald-400/[0.05]"
                                : "")
                            }
                          >
                            <td className="py-2 pr-3 text-slate-200">
                              {source.name}
                              <span className="block font-mono text-[9px] text-slate-500">
                                {source.source_key}
                              </span>
                            </td>
                            <td className="py-2 pr-3 text-slate-400">
                              {humanStatus(source.category)}
                            </td>
                            <td className="py-2 pr-3 text-slate-400">
                              {source.provider}
                            </td>
                            <td className="py-2 pr-3">
                              <StatusPill status={source.validation_status} />
                            </td>
                            <td className="py-2 pr-3 text-[10px] text-slate-500">
                              {formatDate(source.retrieved_at)}
                            </td>
                            <td className="py-2 font-mono text-[9px] text-slate-500">
                              {source.snapshot_sha256
                                ? source.snapshot_sha256.slice(0, 12) + "…"
                                : "None"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <EmptyState
                    title="No infrastructure sources registered"
                    hint="An administrator can register source metadata with provider, license, coverage, CRS, schema and checksum. Registration does not ingest data."
                  />
                )}
              </Card>

              <div className="space-y-4">
                {selectedSource ? (
                  <>
                    <Card
                      title={selectedSource.name}
                      eyebrow={selectedSource.source_key}
                      actions={
                        <StatusPill status={selectedSource.validation_status} />
                      }
                    >
                      <dl className="grid gap-3 sm:grid-cols-2">
                        <KeyValue
                          label="Domain"
                          value={humanStatus(selectedSource.category)}
                        />
                        <KeyValue
                          label="Provider"
                          value={selectedSource.provider}
                        />
                        <KeyValue
                          label="License"
                          value={selectedSource.license_note}
                        />
                        <KeyValue
                          label="Coverage"
                          value={selectedSource.geographic_coverage}
                        />
                        <KeyValue label="CRS" value={selectedSource.crs} />
                        <KeyValue
                          label="Dataset version"
                          value={selectedSource.dataset_version}
                        />
                        <KeyValue
                          label="Schema version"
                          value={selectedSource.schema_version}
                        />
                        <KeyValue
                          label="Update frequency"
                          value={
                            selectedSource.update_frequency ?? "Not recorded"
                          }
                        />
                        <KeyValue
                          label="Retrieved"
                          value={formatDate(selectedSource.retrieved_at)}
                        />
                        <KeyValue
                          label="SHA-256"
                          value={
                            <span className="break-all font-mono text-[9px]">
                              {selectedSource.snapshot_sha256 ?? "Not recorded"}
                            </span>
                          }
                        />
                      </dl>
                      <p className="mt-3 text-[10px] text-slate-500">
                        {selectedSource.known_limitations ??
                          "No known limitations recorded."}
                      </p>
                      <p className="mt-2 text-[10px] text-amber-200/70">
                        {selectedSource.asset_disclaimer}
                      </p>
                      {selectedSource.source_url ? (
                        <a
                          href={selectedSource.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-block text-[11px] text-emerald-300 underline-offset-2 hover:underline"
                        >
                          Open source metadata page
                        </a>
                      ) : null}
                    </Card>

                    <Card title="Metadata payload" eyebrow="Not asset data">
                      <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-white/5 bg-slate-950/50 p-3 text-[10px] text-slate-400">
                        {JSON.stringify(selectedSource.metadata, null, 2)}
                      </pre>
                    </Card>

                    {isAdmin ? (
                      <Card title="Metadata validation" eyebrow="Administrator action">
                        <div className="grid gap-3 sm:grid-cols-[1fr_1.4fr]">
                          <label className="text-[10px] uppercase tracking-wide text-slate-500">
                            Status
                            <select
                              value={sourceStatus}
                              onChange={(event) =>
                                setSourceStatus(event.target.value)
                              }
                              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                            >
                              <option value="VERIFIED">Verified metadata</option>
                              <option value="REJECTED">Rejected</option>
                              <option value="UNAVAILABLE">Unavailable</option>
                            </select>
                          </label>
                          <label className="text-[10px] uppercase tracking-wide text-slate-500">
                            Validation note (required, min 10 characters)
                            <textarea
                              value={sourceNote}
                              onChange={(event) =>
                                setSourceNote(event.target.value)
                              }
                              rows={2}
                              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
                            />
                          </label>
                        </div>
                        {sourceSaveError ? (
                          <div className="mt-3">
                            <ErrorNotice message={sourceSaveError} />
                          </div>
                        ) : null}
                        <button
                          type="button"
                          disabled={
                            sourceSaving || sourceNote.trim().length < 10
                          }
                          onClick={() => void submitSourceValidation()}
                          className="mt-3 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:opacity-40"
                        >
                          {sourceSaving ? "Recording…" : "Record validation"}
                        </button>
                        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                          VERIFIED requires a license, checksum, coverage, CRS,
                          retrieval date and schema version. Verification never
                          downloads or ingests the asset.
                        </p>
                      </Card>
                    ) : null}

                    <Card title="Validation history" eyebrow="Append-only events">
                      {selectedSource.events.length ? (
                        <ol className="space-y-2">
                          {selectedSource.events.map((event) => (
                            <li
                              key={event.id}
                              className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs text-slate-200">
                                  {event.from_status
                                    ? humanStatus(event.from_status) + " → "
                                    : ""}
                                  {humanStatus(event.to_status)}
                                </span>
                                <span className="text-[10px] text-slate-500">
                                  {formatDate(event.created_at)}
                                </span>
                              </div>
                              <p className="mt-1 text-[10px] text-slate-500">
                                {event.actor_email ?? "Unknown actor"} ·{" "}
                                {event.note}
                              </p>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <EmptyState
                          title="No validation events"
                          hint="Registration and validation decisions are recorded separately and never trigger ingestion."
                        />
                      )}
                    </Card>
                  </>
                ) : (
                  <EmptyState
                    title="Select a source"
                    hint="Inspect provider, license, coverage, CRS, version, checksum and validation history."
                  />
                )}
              </div>
            </div>
          </div>
        ) : null}

        {tab === "simulation" ? (
          <div className="space-y-5">
            <Advice>
              Simulation results are illustrative. A passing constraint audit
              does not verify real resource availability, authorize dispatch or
              convert an UNKNOWN capability into an available one.
            </Advice>
            {simulationError ? (
              <ErrorNotice message={simulationError} onRetry={loadSimulation} />
            ) : null}
            {simulation ? (
              <>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  {[
                    ["Simulations", simulation.summary.simulations],
                    ["Pass", simulation.summary.pass],
                    ["Fail", simulation.summary.fail],
                    ["Unknown", simulation.summary.unknown],
                    [
                      "Human approved",
                      simulation.summary.with_approved_review,
                    ],
                  ].map(([label, value]) => (
                    <div
                      key={String(label)}
                      className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3"
                    >
                      <p className="text-[10px] uppercase tracking-wide text-slate-500">
                        {label}
                      </p>
                      <p className="mt-1 text-xl font-semibold text-white">
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
                {simulation.simulations.length === 0 ? (
                  <EmptyState
                    title="No decision simulations"
                    hint="The audit inspects persisted simulations for recorded objectives, constraints, reproducibility, human review and preserved UNKNOWN resources."
                  />
                ) : null}
                <div className="space-y-4">
                  {simulation.simulations.map((item) => (
                    <Card
                      key={item.id}
                      title={
                        item.scenario.name ??
                        "Scenario " + item.scenario.id.slice(0, 8)
                      }
                      eyebrow={item.strategy}
                      actions={
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
                            SIMULATED
                          </span>
                          <StatusPill status={item.validation_status} />
                        </div>
                      }
                    >
                      <dl className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
                        <KeyValue
                          label="Model"
                          value={item.model_version}
                        />
                        <KeyValue
                          label="Objective"
                          value={formatNumber(item.objective.score)}
                        />
                        <KeyValue
                          label="Actions"
                          value={item.plan_summary.total_actions}
                        />
                        <KeyValue
                          label="Resources"
                          value={item.plan_summary.resources_used}
                        />
                        <KeyValue
                          label="Unknown resources"
                          value={item.plan_summary.unknown_resources}
                        />
                      </dl>
                      <div className="mt-4 grid gap-2 md:grid-cols-2">
                        {item.checks.map((check) => (
                          <div
                            key={check.key}
                            className="rounded-lg border border-white/5 bg-slate-950/40 px-3 py-2"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="text-xs font-medium text-slate-200">
                                {check.label}
                              </span>
                              <StatusPill status={check.status} />
                            </div>
                            <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
                              {check.evidence}
                            </p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="text-[10px] uppercase tracking-wide text-slate-500">
                            Assumptions
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4 text-[10px] text-slate-400">
                            {item.assumptions.length ? (
                              item.assumptions.map((assumption) => (
                                <li key={assumption}>{assumption}</li>
                              ))
                            ) : (
                              <li>No assumptions recorded.</li>
                            )}
                          </ul>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-wide text-slate-500">
                            Limitations and warnings
                          </p>
                          <ul className="mt-1 list-disc space-y-1 pl-4 text-[10px] text-slate-400">
                            {[...item.limitations, ...item.warnings].length ? (
                              [...item.limitations, ...item.warnings].map(
                                (warning) => <li key={warning}>{warning}</li>,
                              )
                            ) : (
                              <li>No warnings recorded.</li>
                            )}
                          </ul>
                        </div>
                      </div>
                      <div className="mt-3 rounded-lg border border-white/5 bg-slate-950/40 p-3">
                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                          Human reviews
                        </p>
                        {item.human_reviews.length ? (
                          <ul className="mt-1 space-y-1 text-[10px] text-slate-400">
                            {item.human_reviews.map((review) => (
                              <li key={review.id}>
                                {humanStatus(review.status)} ·{" "}
                                {formatDate(review.created_at)} ·{" "}
                                {review.reviewed_by ?? "Unknown reviewer"}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-1 text-[10px] text-slate-500">
                            No decision review recorded.
                          </p>
                        )}
                      </div>
                      <p className="mt-3 text-[10px] text-slate-500">
                        {item.note} Execution permitted:{" "}
                        {item.dispatch_permitted ? "yes" : "no"}. Resource
                        allocation permitted:{" "}
                        {item.resource_allocation_permitted ? "yes" : "no"}.
                      </p>
                    </Card>
                  ))}
                </div>
                <Card title="Audit limitations" eyebrow="Not an execution review">
                  <ul className="list-disc space-y-1 pl-4 text-[11px] leading-relaxed text-slate-400">
                    {simulation.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <p className="mt-3 text-[10px] text-slate-500">
                    Execution authorized by this audit:{" "}
                    {simulation.execution_authorized ? "yes" : "no"}. Protocol{" "}
                    {simulation.protocol}.
                  </p>
                </Card>
              </>
            ) : simulationError ? null : (
              <LoadingBlock label="Auditing persisted simulation constraints…" />
            )}
          </div>
        ) : null}

        {tab === "evidence" ? <EvidenceWorkspace /> : null}
      </section>
    </main>
  );
}
