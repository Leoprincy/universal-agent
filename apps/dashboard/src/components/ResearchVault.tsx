import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  Database,
  ExternalLink,
  Filter,
  LoaderCircle,
  Pencil,
  Plus,
  Quote,
  Search,
  Trash2,
  X,
} from "lucide-react";
import {
  createResearchRecord,
  deleteResearchRecord,
  listResearchRecords,
  updateResearchRecord,
} from "../lib/api";
import type {
  Project,
  ResearchRecord,
  ResearchRecordCreateInput,
  SourceType,
} from "../types";

const SOURCE_TYPE_OPTIONS: { value: SourceType; label: string; desc: string }[] = [
  { value: "user_interview", label: "User Interview", desc: "First-hand qualitative feedback from real users" },
  { value: "app_review", label: "App Review", desc: "Public store reviews (Google Play, iOS App Store)" },
  { value: "competitor_analysis", label: "Competitor Analysis", desc: "Teardown or audit of competitor feature/pricing" },
  { value: "analytics", label: "Telemetry & Analytics", desc: "Quantitative metrics, funnel drop-off, behavioral data" },
  { value: "market_report", label: "Market Report", desc: "Third-party industry analysis, papers, or benchmark studies" },
  { value: "manual_observation", label: "Manual Observation", desc: "Direct product observation by team or operator" },
];

export function ResearchVault({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const [records, setRecords] = useState<ResearchRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<ResearchRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0];

  const fetchRecords = useCallback(async () => {
    if (!activeProject) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listResearchRecords(activeProject.id, {
        source_type: filterType || undefined,
        limit: 100,
      });
      setRecords(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load research records");
    } finally {
      setLoading(false);
    }
  }, [activeProject, filterType]);

  useEffect(() => {
    void fetchRecords();
  }, [fetchRecords]);

  const handleDelete = async (recordId: string) => {
    if (!window.confirm("Are you sure you want to delete this research record?")) return;
    try {
      await deleteResearchRecord(activeProject.id, recordId);
      setRecords((prev) => prev.filter((r) => r.id !== recordId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete record");
    }
  };

  const filteredRecords = records.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      r.title.toLowerCase().includes(q) ||
      r.observation_summary.toLowerCase().includes(q) ||
      (r.source_quote && r.source_quote.toLowerCase().includes(q)) ||
      (r.source_name && r.source_name.toLowerCase().includes(q))
    );
  });

  if (!activeProject) {
    return (
      <div className="p-8 text-center text-neutral-400">
        Please create a project first before viewing the Research Vault.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Vault Heading & Project Context */}
      <div className="flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> RESEARCH REPOSITORY</div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Research Vault<span className="heading-period">.</span>
          </h1>
          <p className="page-subtitle">
            Ground growth decisions with verifiable evidence, factual observations, and transparent provenance.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {projects.length > 1 && (
            <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs">
              <span className="text-neutral-400">Project:</span>
              <select
                className="bg-transparent text-white font-semibold focus:outline-none"
                value={activeProject.id}
                onChange={(e) => onSelectProject(e.target.value)}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-neutral-900 text-white">
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button
            className="button button-primary"
            onClick={() => {
              setEditingRecord(null);
              setModalOpen(true);
            }}
          >
            <Plus size={15} /> Add Evidence
          </button>
        </div>
      </div>

      {error && (
        <div className="workspace-alert" role="alert">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
          <button className="icon-button" onClick={() => setError(null)}><X size={14} /></button>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="flex items-center justify-between gap-4 p-3 rounded-xl bg-surface border border-white/10">
        <div className="flex items-center gap-2 flex-1 max-w-md bg-canvas rounded-lg px-3 py-2 border border-white/10 text-xs">
          <Search size={14} className="text-neutral-400" />
          <input
            type="text"
            className="bg-transparent text-white w-full focus:outline-none placeholder:text-neutral-500"
            placeholder="Search evidence by title, summary, quote, or source..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")}><X size={13} className="text-neutral-400" /></button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Filter size={14} className="text-neutral-400" />
          <select
            className="bg-canvas border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="">All Source Types</option>
            {SOURCE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Records Grid */}
      {loading ? (
        <div className="p-12 text-center text-neutral-400 flex flex-col items-center gap-3">
          <LoaderCircle size={24} className="spin text-violet-400" />
          <span className="text-xs">Loading evidence records...</span>
        </div>
      ) : filteredRecords.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-white/15 bg-white/[0.02] flex flex-col items-center gap-3">
          <Database size={28} className="text-neutral-500" />
          <div>
            <h3 className="text-sm font-semibold text-white">No research records found</h3>
            <p className="text-xs text-neutral-400 mt-1 max-w-sm">
              {filterType || searchQuery
                ? "No evidence matches your active filter or search query."
                : "Capture user interviews, store reviews, competitor audits, and analytics here to substantiate growth opportunities."}
            </p>
          </div>
          <button
            className="button button-secondary text-xs"
            onClick={() => {
              setEditingRecord(null);
              setModalOpen(true);
            }}
          >
            <Plus size={14} /> Add First Evidence Item
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredRecords.map((r) => (
            <div
              key={r.id}
              className="p-5 rounded-2xl bg-surface border border-white/10 flex flex-col justify-between gap-4 hover:border-violet-500/30 transition-colors"
            >
              <div className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge badge-active text-[10px] uppercase tracking-wider">
                      {r.source_type.replace("_", " ")}
                    </span>
                    {r.source_name && (
                      <span className="text-xs text-neutral-400 font-medium">
                        {r.source_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      className="icon-button"
                      onClick={() => {
                        setEditingRecord(r);
                        setModalOpen(true);
                      }}
                      title="Edit research"
                    >
                      <Pencil size={13} />
                    </button>
                    <button
                      className="icon-button text-neutral-400 hover:text-rose-400"
                      onClick={() => handleDelete(r.id)}
                      title="Delete research"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                <h3 className="text-base font-bold text-white">{r.title}</h3>

                {/* 1. Verbatim Evidence Quote */}
                {r.source_quote && (
                  <div className="p-3 rounded-lg bg-black/40 border border-white/5 text-xs text-neutral-300 italic flex items-start gap-2">
                    <Quote size={14} className="text-violet-400 shrink-0 mt-0.5" />
                    <span>"{r.source_quote}"</span>
                  </div>
                )}

                {/* 2. Observation Summary */}
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider text-neutral-400 block mb-1">
                    Factual Observation
                  </span>
                  <p className="text-xs text-neutral-200 leading-relaxed">
                    {r.observation_summary}
                  </p>
                </div>

                {/* 3. Analytical Interpretation */}
                {r.interpretation_notes && (
                  <div className="pt-2 border-t border-white/5">
                    <span className="text-[10px] uppercase font-bold tracking-wider text-violet-400 block mb-1">
                      Analytical Interpretation
                    </span>
                    <p className="text-xs text-neutral-400 italic leading-relaxed">
                      {r.interpretation_notes}
                    </p>
                  </div>
                )}

                {/* Structured Evidence Data */}
                {r.evidence_data && Object.keys(r.evidence_data).length > 0 && (
                  <div className="p-2.5 rounded bg-white/[0.03] border border-white/5 font-mono text-[11px] text-neutral-300">
                    <pre className="overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(r.evidence_data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              {/* Provenance Footer */}
              <div className="pt-3 border-t border-white/10 flex flex-wrap items-center justify-between gap-2 text-[11px] text-neutral-500">
                <div className="flex items-center gap-3">
                  {r.source_url && (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-violet-400 hover:underline flex items-center gap-1"
                    >
                      Source Link <ExternalLink size={10} />
                    </a>
                  )}
                  {r.observed_at && (
                    <span>Observed: {new Date(r.observed_at).toLocaleDateString()}</span>
                  )}
                  {r.published_at && (
                    <span>Published: {new Date(r.published_at).toLocaleDateString()}</span>
                  )}
                </div>
                <span>Collected: {new Date(r.collected_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <ResearchModal
          projectId={activeProject.id}
          editingRecord={editingRecord}
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onSaved={() => {
            setModalOpen(false);
            void fetchRecords();
          }}
        />
      )}
    </div>
  );
}

// ─── Research Creation & Editing Modal ────────────────────────────────────────

function ResearchModal({
  projectId,
  editingRecord,
  isOpen,
  onClose,
  onSaved,
}: {
  projectId: string;
  editingRecord: ResearchRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(editingRecord?.title ?? "");
  const [sourceType, setSourceType] = useState<SourceType>(
    editingRecord?.source_type ?? "user_interview"
  );
  const [sourceUrl, setSourceUrl] = useState(editingRecord?.source_url ?? "");
  const [sourceName, setSourceName] = useState(editingRecord?.source_name ?? "");
  const [author, setAuthor] = useState(editingRecord?.author ?? "");
  const [sourceQuote, setSourceQuote] = useState(editingRecord?.source_quote ?? "");
  const [observationSummary, setObservationSummary] = useState(
    editingRecord?.observation_summary ?? ""
  );
  const [interpretationNotes, setInterpretationNotes] = useState(
    editingRecord?.interpretation_notes ?? ""
  );
  const [evidenceDataStr, setEvidenceDataStr] = useState(
    editingRecord?.evidence_data ? JSON.stringify(editingRecord.evidence_data, null, 2) : ""
  );
  const [observedAt, setObservedAt] = useState(
    editingRecord?.observed_at ? editingRecord.observed_at.substring(0, 10) : ""
  );
  const [publishedAt, setPublishedAt] = useState(
    editingRecord?.published_at ? editingRecord.published_at.substring(0, 10) : ""
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Parse evidence_data if supplied
    let parsedEvidence: Record<string, unknown> | undefined = undefined;
    if (evidenceDataStr.trim()) {
      try {
        parsedEvidence = JSON.parse(evidenceDataStr);
        if (typeof parsedEvidence !== "object" || parsedEvidence === null || Array.isArray(parsedEvidence)) {
          throw new Error("Must be a JSON object dictionary");
        }
      } catch (err) {
        setError(`Invalid JSON in Evidence Data: ${err instanceof Error ? err.message : "Parse error"}`);
        return;
      }
    }

    // Source-type client validations
    if (sourceType === "user_interview" && !sourceName.trim()) {
      setError("User interviews require a source identifier (e.g. participant role or cohort).");
      return;
    }
    if (sourceType === "app_review") {
      if (!sourceName.trim()) {
        setError("App reviews require source_name (e.g. Google Play Store).");
        return;
      }
      if (!sourceQuote.trim()) {
        setError("App reviews require verbatim source_quote.");
        return;
      }
    }
    if (sourceType === "competitor_analysis" && !sourceUrl.trim() && !sourceName.trim()) {
      setError("Competitor analysis requires either a source_url or source_name.");
      return;
    }
    if (sourceType === "analytics") {
      if (!parsedEvidence || Object.keys(parsedEvidence).length === 0) {
        setError("Analytics records require non-empty JSON metrics in Evidence Data.");
        return;
      }
      const hasNumeric = Object.values(parsedEvidence).some(
        (v) => typeof v === "number" && !isNaN(v)
      );
      if (!hasNumeric) {
        setError("Analytics evidence data must contain at least one numeric metric observation (e.g. churn_rate: 0.42).");
        return;
      }
    }
    if (sourceType === "market_report") {
      if (!sourceName.trim()) {
        setError("Market reports require source_name (publishing entity).");
        return;
      }
      if (!sourceUrl.trim() && !author.trim()) {
        setError("Market reports require at least one of source_url or author.");
        return;
      }
    }
    if (!observationSummary.trim()) {
      setError("Observation summary is mandatory.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: ResearchRecordCreateInput = {
        title: title.trim(),
        source_type: sourceType,
        source_url: sourceUrl.trim() || undefined,
        source_name: sourceName.trim() || undefined,
        author: author.trim() || undefined,
        source_quote: sourceQuote.trim() || undefined,
        observation_summary: observationSummary.trim(),
        interpretation_notes: interpretationNotes.trim() || undefined,
        evidence_data: parsedEvidence,
        observed_at: observedAt ? new Date(observedAt).toISOString() : undefined,
        published_at: publishedAt ? new Date(publishedAt).toISOString() : undefined,
      };

      if (editingRecord) {
        await updateResearchRecord(projectId, editingRecord.id, payload);
      } else {
        await createResearchRecord(projectId, payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save research record");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card max-w-2xl w-full max-h-[90vh] flex flex-col">
        <div className="modal-header">
          <div>
            <h3 className="text-base font-bold text-white">
              {editingRecord ? "Edit Research Record" : "Add Verifiable Evidence"}
            </h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Distinguish what was observed from analytical interpretations.
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto flex flex-col gap-4">
          {error && (
            <div className="flex items-center gap-2 text-rose-400 text-xs bg-rose-500/10 p-3 rounded-lg border border-rose-500/20">
              <AlertCircle size={15} />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">Title *</label>
            <input
              type="text"
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              placeholder="e.g. Student survey shows drop-off when resume upload hangs"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">Source Type *</label>
              <select
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as SourceType)}
              >
                {SOURCE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-neutral-900 text-white">
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">
                Source Name / Platform {sourceType === "user_interview" || sourceType === "app_review" || sourceType === "market_report" ? "*" : ""}
              </label>
              <input
                type="text"
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                placeholder={sourceType === "user_interview" ? "e.g. Participant #42 (Retail Shift Worker)" : "e.g. Google Play Store"}
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">Source URL</label>
              <input
                type="url"
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                placeholder="https://..."
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">Author / Contributor</label>
              <input
                type="text"
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                placeholder="e.g. Jane Doe, Senior Analyst"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
              />
            </div>
          </div>

          {/* Verbatim Source Quote */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Verbatim Evidence Quote {sourceType === "app_review" ? "*" : "(Optional)"}
            </label>
            <textarea
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={2}
              placeholder="Exact words or metric excerpt from the primary source..."
              value={sourceQuote}
              onChange={(e) => setSourceQuote(e.target.value)}
            />
          </div>

          {/* Factual Observation Summary */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Observation Summary (Factual, no speculation) *
            </label>
            <textarea
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={3}
              placeholder="Factual statement of what was noticed without hypothesizing solution..."
              value={observationSummary}
              onChange={(e) => setObservationSummary(e.target.value)}
            />
          </div>

          {/* Analytical Interpretation */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Interpretation Notes (Analysis & Context) <span className="text-neutral-500">(Optional)</span>
            </label>
            <textarea
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={2}
              placeholder="What this observation might mean for the product or market..."
              value={interpretationNotes}
              onChange={(e) => setInterpretationNotes(e.target.value)}
            />
          </div>

          {/* Evidence Data (JSON) */}
          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Structured Evidence Data (JSON object) {sourceType === "analytics" ? "*" : ""}
            </label>
            <textarea
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs font-mono text-white focus:outline-none focus:border-violet-500"
              rows={3}
              placeholder='{"rating": 1, "app_version": "2.4.1", "dropoff_rate": 0.42}'
              value={evidenceDataStr}
              onChange={(e) => setEvidenceDataStr(e.target.value)}
            />
          </div>

          {/* Provenance Dates */}
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-white/10">
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">
                Observed Date <span className="text-neutral-500">(Leave blank if unknown)</span>
              </label>
              <input
                type="date"
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-violet-500"
                value={observedAt}
                onChange={(e) => setObservedAt(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">
                Published Date <span className="text-neutral-500">(Leave blank if unknown)</span>
              </label>
              <input
                type="date"
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-violet-500"
                value={publishedAt}
                onChange={(e) => setPublishedAt(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-white/10">
            <button
              type="button"
              className="button button-quiet text-xs"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="button button-primary text-xs"
              disabled={submitting}
            >
              {submitting ? "Saving..." : editingRecord ? "Update Record" : "Save Record"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
