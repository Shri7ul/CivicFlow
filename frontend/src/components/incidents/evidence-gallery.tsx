"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { getEvidenceUrl, uploadIncidentEvidence } from "@/lib/api/evidence";
import {
  formatFileSize,
  MAX_EVIDENCE_FILES,
  validateEvidenceFiles,
} from "@/lib/evidence";
import { formatDateTime } from "@/lib/incidents";
import type { Evidence } from "@/types/incidents";

type EvidenceGalleryProps = {
  incidentId: string;
  evidence: Evidence[];
  canUpload: boolean;
  onUploaded: (evidence: Evidence[]) => void;
};

const inputClass =
  "block w-full rounded-xl border border-dashed border-white/20 bg-slate-950/60 px-4 py-4 text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-400 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-950";

export function EvidenceGallery({
  incidentId,
  evidence,
  canUpload,
  onUploaded,
}: EvidenceGalleryProps) {
  const { apiRequest, uploadRequest } = useAuth();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [urlsLoading, setUrlsLoading] = useState(false);
  const [urlsError, setUrlsError] = useState<string | null>(null);
  const urlRequestRef = useRef(0);

  const refreshUrls = useCallback(async () => {
    const requestId = ++urlRequestRef.current;
    if (evidence.length === 0) {
      setUrls({});
      setUrlsError(null);
      return;
    }
    setUrlsLoading(true);
    setUrlsError(null);
    const entries = await Promise.all(
      evidence.map(async (item) => {
        try {
          const result = await getEvidenceUrl(apiRequest, incidentId, item.id);
          return [item.id, result.signed_url] as const;
        } catch {
          return [item.id, ""] as const;
        }
      }),
    );
    if (requestId !== urlRequestRef.current) {
      return;
    }
    setUrls(Object.fromEntries(entries));
    if (entries.some(([, url]) => !url)) {
      setUrlsError("Some previews could not be loaded. Try refreshing.");
    }
    setUrlsLoading(false);
  }, [apiRequest, evidence, incidentId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshUrls();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshUrls]);

  function onFilesChange(files: FileList | null) {
    setUploadError(null);
    setProgress(0);
    setSelectedFiles(Array.from(files ?? []));
  }

  async function upload() {
    const validation = validateEvidenceFiles(selectedFiles);
    if (validation) {
      setUploadError(validation);
      return;
    }
    setUploading(true);
    setProgress(0);
    setUploadError(null);
    try {
      const uploaded = await uploadIncidentEvidence(
        uploadRequest,
        incidentId,
        selectedFiles,
        setProgress,
      );
      onUploaded(uploaded);
      setSelectedFiles([]);
      setProgress(0);
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Unable to upload evidence.",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <section
      id="evidence"
      className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-6 sm:p-8"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Photo evidence</h2>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Private images. Previews use short-lived signed links.
          </p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-semibold text-slate-300">
          {evidence.length} file{evidence.length === 1 ? "" : "s"}
        </span>
      </div>

      {canUpload ? (
        <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <label htmlFor="evidence-files" className="sr-only">
            Add photo evidence
          </label>
          <input
            id="evidence-files"
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) => onFilesChange(event.target.files)}
            disabled={uploading}
            className={inputClass}
          />
          <p className="mt-2 text-[11px] text-slate-500">
            JPEG, PNG, or WebP · max 10 MB each · up to {MAX_EVIDENCE_FILES} at
            once.
          </p>

          {selectedFiles.length > 0 ? (
            <ul className="mt-3 space-y-1.5 text-xs text-slate-300">
              {selectedFiles.map((file) => (
                <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                  {file.name} · {formatFileSize(file.size)}
                </li>
              ))}
            </ul>
          ) : null}

          {uploading ? (
            <div className="mt-3">
              <div
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress}
                aria-label="Evidence upload progress"
                className="h-2 overflow-hidden rounded-full bg-white/10"
              >
                <div
                  className="h-full rounded-full bg-emerald-400 transition-[width]"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Uploading… {progress}%
              </p>
            </div>
          ) : null}

          {uploadError ? (
            <p role="alert" className="mt-3 text-xs text-rose-200">
              {uploadError}
            </p>
          ) : null}

          <button
            type="button"
            onClick={() => void upload()}
            disabled={uploading || selectedFiles.length === 0}
            className="mt-4 rounded-lg bg-emerald-400 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:opacity-50"
          >
            {uploading
              ? "Uploading…"
              : uploadError
                ? "Retry upload"
                : "Upload evidence"}
          </button>
        </div>
      ) : null}

      {evidence.length === 0 ? (
        <p className="mt-5 rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-slate-500">
          No photos attached yet.
        </p>
      ) : (
        <>
          <div className="mt-5 flex items-center justify-between gap-2">
            <p className="text-[11px] text-slate-500">
              {urlsLoading ? "Loading private previews…" : "Private previews"}
            </p>
            <button
              type="button"
              onClick={() => void refreshUrls()}
              disabled={urlsLoading}
              className="rounded-lg border border-white/10 px-2.5 py-1 text-[11px] text-slate-300 disabled:opacity-50"
            >
              Refresh links
            </button>
          </div>
          {urlsError ? (
            <p role="alert" className="mt-2 text-xs text-rose-200">
              {urlsError}
            </p>
          ) : null}
          <ul className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {evidence.map((item) => {
              const url = urls[item.id];
              return (
                <li
                  key={item.id}
                  className="overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60"
                >
                  <div className="flex aspect-[4/3] items-center justify-center bg-black/20">
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="block h-full w-full"
                      >
                        {/* Signed Storage URLs are not compatible with next/image. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={url}
                          alt={item.file_name}
                          loading="lazy"
                          referrerPolicy="no-referrer"
                          className="h-full w-full object-cover"
                        />
                      </a>
                    ) : (
                      <span className="px-3 text-center text-[11px] text-slate-500">
                        {urlsLoading ? "Loading preview…" : "Preview unavailable"}
                      </span>
                    )}
                  </div>
                  <div className="p-3">
                    <p className="truncate text-xs font-medium text-slate-200">
                      {item.file_name}
                    </p>
                    <p className="mt-1 text-[10px] text-slate-500">
                      {formatFileSize(item.file_size)} ·{" "}
                      {formatDateTime(item.created_at)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
