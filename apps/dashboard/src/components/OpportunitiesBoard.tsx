import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  LoaderCircle,
  Plus,
  X,
} from "lucide-react";
import {
  createOpportunity,
  listOpportunities,
  transitionOpportunity,
} from "../lib/api";
import type {
  Opportunity,
  OpportunityCategory,
  OpportunityCreateInput,
  OpportunityEffort,
  OpportunityImpact,
  OpportunityPriority,
  OpportunityStatus,
  Project,
} from "../types";
import { EvidenceLinkerModal } from "./EvidenceLinkerModal";
import { OpportunityDrawer } from "./OpportunityDrawer";

const STATUS_COLUMNS: { status: OpportunityStatus; label: string; tone: string }[] = [
  { status: "draft", label: "Draft Ideas", tone: "neutral" },
  { status: "in_review", label: "Under Review", tone: "amber" },
  { status: "approved", label: "Approved for Plan", tone: "emerald" },
  { status: "rejected", label: "Rejected", tone: "rose" },
  { status: "archived", label: "Archived", tone: "neutral" },
];

const CATEGORY_OPTIONS: { value: OpportunityCategory; label: string }[] = [
  { value: "acquisition", label: "Acquisition" },
  { value: "activation", label: "Activation" },
  { value: "retention", label: "Retention" },
  { value: "referral", label: "Referral" },
  { value: "revenue", label: "Revenue" },
  { value: "experimentation", label: "Experimentation" },
];

const PRIORITY_MATRIX: Record<string, OpportunityPriority> = {
  "critical-low": "p0_urgent",
  "critical-medium": "p0_urgent",
  "critical-high": "p1_high",
  "high-low": "p0_urgent",
  "high-medium": "p1_high",
  "high-high": "p2_medium",
  "medium-low": "p1_high",
  "medium-medium": "p2_medium",
  "medium-high": "p3_low",
  "low-low": "p2_medium",
  "low-medium": "p3_low",
  "low-high": "p3_low",
};

function calculateLocalPriority(
  impact: OpportunityImpact,
  effort: OpportunityEffort
): OpportunityPriority {
  return PRIORITY_MATRIX[`${impact}-${effort}`] ?? "p2_medium";
}

export function OpportunitiesBoard({
  projects,
  activeProjectId,
  onSelectProject,
}: {
  projects: Project[];
  activeProjectId: string;
  onSelectProject: (id: string) => void;
}) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [linkerOpen, setLinkerOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? projects[0];

  const fetchOpportunities = useCallback(async () => {
    if (!activeProject) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listOpportunities(activeProject.id, {
        category: categoryFilter || undefined,
        priority: priorityFilter || undefined,
        limit: 100,
      });
      setOpportunities(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load opportunities");
    } finally {
      setLoading(false);
    }
  }, [activeProject, categoryFilter, priorityFilter]);

  useEffect(() => {
    void fetchOpportunities();
  }, [fetchOpportunities]);

  const handleTransition = async (
    opp: Opportunity,
    targetStatus: OpportunityStatus,
    reason?: string
  ): Promise<Opportunity> => {
    const updated = await transitionOpportunity(activeProject.id, opp.id, {
      status: targetStatus,
      reason,
    });
    setOpportunities((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    if (selectedOpportunity && selectedOpportunity.id === updated.id) {
      setSelectedOpportunity(updated);
    }
    return updated;
  };

  const getPriorityLabel = (priority: OpportunityPriority) => {
    switch (priority) {
      case "p0_urgent":
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">P0 • Critical</span>;
      case "p1_high":
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">P1 • High</span>;
      case "p2_medium":
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">P2 • Medium</span>;
      case "p3_low":
        return <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-neutral-500/20 text-neutral-300 border border-neutral-500/30">P3 • Low</span>;
    }
  };

  if (!activeProject) {
    return (
      <div className="p-8 text-center text-neutral-400">
        Please create a project first before managing opportunities.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Board Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> GROWTH DISCOVERY</div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            Growth Opportunities<span className="heading-period">.</span>
          </h1>
          <p className="page-subtitle">
            Structured candidate initiatives linking hypotheses to verifiable evidence and review workflows.
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
          <button className="button button-primary" onClick={() => setModalOpen(true)}>
            <Plus size={15} /> New Opportunity
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

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-4 p-3 rounded-xl bg-surface border border-white/10">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Filters:</span>
          <select
            className="bg-canvas border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">All Categories</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>

          <select
            className="bg-canvas border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
          >
            <option value="">All Priorities</option>
            <option value="p0_urgent">P0 • Critical</option>
            <option value="p1_high">P1 • High</option>
            <option value="p2_medium">P2 • Medium</option>
            <option value="p3_low">P3 • Low</option>
          </select>
        </div>

        <span className="text-xs text-neutral-400">
          Showing <strong>{opportunities.length}</strong> opportunities
        </span>
      </div>

      {/* Kanban Board Columns */}
      {loading ? (
        <div className="p-12 text-center text-neutral-400 flex flex-col items-center gap-3">
          <LoaderCircle size={24} className="spin text-violet-400" />
          <span className="text-xs">Loading opportunities board...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 items-start">
          {STATUS_COLUMNS.map(({ status, label }) => {
            const columnOpps = opportunities.filter((o) => o.status === status);
            return (
              <div
                key={status}
                className="flex flex-col gap-3 rounded-2xl bg-surface/60 border border-white/10 p-3 min-h-[500px]"
              >
                <div className="flex items-center justify-between pb-2 border-b border-white/10 px-1">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">{label}</h3>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-white/10 text-neutral-300">
                    {columnOpps.length}
                  </span>
                </div>

                <div className="flex flex-col gap-3 flex-1">
                  {columnOpps.length === 0 ? (
                    <div className="p-4 text-center text-[11px] text-neutral-500 rounded-lg border border-dashed border-white/5 bg-white/[0.01]">
                      No items
                    </div>
                  ) : (
                    columnOpps.map((opp) => (
                      <div
                        key={opp.id}
                        className="p-3.5 rounded-xl bg-canvas border border-white/10 hover:border-violet-500/40 cursor-pointer transition-all flex flex-col gap-2.5 shadow-sm"
                        onClick={() => setSelectedOpportunity(opp)}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="badge text-[10px]">{opp.category}</span>
                          {getPriorityLabel(opp.priority)}
                        </div>

                        <h4 className="text-xs font-bold text-white leading-snug">{opp.title}</h4>

                        <p className="text-[11px] text-neutral-400 line-clamp-2 leading-relaxed font-mono bg-black/20 p-1.5 rounded">
                          {opp.hypothesis}
                        </p>

                        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[10px] text-neutral-500">
                          <span className="capitalize">{opp.estimated_impact} impact</span>
                          <span>
                            {opp.confidence_score !== null && opp.confidence_score !== undefined
                              ? `${(opp.confidence_score * 100).toFixed(0)}% conf`
                              : "No conf"}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Opportunity Detail Drawer */}
      {selectedOpportunity && (
        <OpportunityDrawer
          opportunity={selectedOpportunity}
          projectId={activeProject.id}
          onClose={() => setSelectedOpportunity(null)}
          onOpportunityUpdated={(updated) => {
            setOpportunities((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
            setSelectedOpportunity(updated);
          }}
          onOpenLinker={() => setLinkerOpen(true)}
          onTransition={handleTransition}
        />
      )}

      {/* Evidence Linker Modal */}
      {linkerOpen && selectedOpportunity && (
        <EvidenceLinkerModal
          opportunity={selectedOpportunity}
          projectId={activeProject.id}
          isOpen={linkerOpen}
          onClose={() => setLinkerOpen(false)}
          onLinked={() => {
            // Trigger refresh of drawer by re-setting opportunity
            setSelectedOpportunity({ ...selectedOpportunity });
          }}
        />
      )}

      {/* New Opportunity Modal */}
      {modalOpen && (
        <NewOpportunityModal
          projectId={activeProject.id}
          isOpen={modalOpen}
          onClose={() => setModalOpen(false)}
          onCreated={(newOpp) => {
            setOpportunities((prev) => [newOpp, ...prev]);
            setModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

// ─── New Opportunity Modal ───────────────────────────────────────────────────

function NewOpportunityModal({
  projectId,
  isOpen,
  onClose,
  onCreated,
}: {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onCreated: (opp: Opportunity) => void;
}) {
  const [title, setTitle] = useState("");
  const [problemStatement, setProblemStatement] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [proposedMechanism, setProposedMechanism] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [category, setCategory] = useState<OpportunityCategory>("activation");
  const [impact, setImpact] = useState<OpportunityImpact>("medium");
  const [effort, setEffort] = useState<OpportunityEffort>("medium");
  const [confidenceScore, setConfidenceScore] = useState<string>("0.75");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const computedPriority = calculateLocalPriority(impact, effort);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const confNum = confidenceScore.trim() ? parseFloat(confidenceScore) : undefined;
    if (confNum !== undefined && (isNaN(confNum) || confNum < 0 || confNum > 1)) {
      setError("Confidence score must be a number between 0.00 and 1.00.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: OpportunityCreateInput = {
        title: title.trim(),
        problem_statement: problemStatement.trim(),
        hypothesis: hypothesis.trim(),
        proposed_mechanism: proposedMechanism.trim(),
        target_audience: targetAudience.trim(),
        category,
        estimated_impact: impact,
        estimated_effort: effort,
        confidence_score: confNum,
      };

      const created = await createOpportunity(projectId, payload);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create opportunity");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card max-w-2xl w-full max-h-[90vh] flex flex-col">
        <div className="modal-header">
          <div>
            <h3 className="text-base font-bold text-white">Synthesize Growth Opportunity</h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Draft a testable growth initiative adhering to the 4-part taxonomy.
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
            <label className="block text-xs font-semibold text-neutral-300 mb-1">Opportunity Title *</label>
            <input
              type="text"
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              placeholder="e.g. One-Tap Quick Apply for Student Job Seekers"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">Category *</label>
              <select
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                value={category}
                onChange={(e) => setCategory(e.target.value as OpportunityCategory)}
              >
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value} className="bg-neutral-900 text-white">
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-300 mb-1">Target Audience *</label>
              <input
                type="text"
                required
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                placeholder="e.g. University students seeking retail shifts"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
              />
            </div>
          </div>

          {/* 1. Problem Statement */}
          <div>
            <label className="block text-xs font-semibold text-rose-300 mb-1">
              1. Problem Statement (Factual user pain or market gap) *
            </label>
            <textarea
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={2}
              placeholder="What friction exists? e.g. Students abandon checkout when asked to re-enter resume details..."
              value={problemStatement}
              onChange={(e) => setProblemStatement(e.target.value)}
            />
          </div>

          {/* 2. Hypothesis */}
          <div>
            <label className="block text-xs font-semibold text-violet-300 mb-1">
              2. Falsifiable Hypothesis (Cause-and-effect prediction) *
            </label>
            <textarea
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500 font-mono text-[11px]"
              rows={2}
              placeholder="If we [action], then [measurable metric] will increase by [X] because [rationale]..."
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
            />
          </div>

          {/* 3. Proposed Mechanism */}
          <div>
            <label className="block text-xs font-semibold text-blue-300 mb-1">
              3. Proposed Mechanism (Product/technical change) *
            </label>
            <textarea
              required
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={2}
              placeholder="The vehicle that tests the hypothesis, e.g. Cache profile document on client device..."
              value={proposedMechanism}
              onChange={(e) => setProposedMechanism(e.target.value)}
            />
          </div>

          {/* Impact, Effort & Deterministic Priority Live Preview */}
          <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-white/5 border border-white/10 items-center">
            <div>
              <label className="block text-[10px] uppercase font-bold text-neutral-400 mb-1">Impact</label>
              <select
                className="w-full bg-canvas border border-white/10 rounded-lg p-2 text-xs text-white focus:outline-none"
                value={impact}
                onChange={(e) => setImpact(e.target.value as OpportunityImpact)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-neutral-400 mb-1">Effort</label>
              <select
                className="w-full bg-canvas border border-white/10 rounded-lg p-2 text-xs text-white focus:outline-none"
                value={effort}
                onChange={(e) => setEffort(e.target.value as OpportunityEffort)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-neutral-400 mb-1">
                Deterministic Priority
              </label>
              <div className="p-2 rounded-lg bg-black/40 text-xs font-mono text-center font-bold text-violet-300 border border-white/5">
                {computedPriority}
              </div>
            </div>
          </div>

          {/* Confidence Score */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-neutral-300">
                Confidence Score (0.00 – 1.00)
              </label>
              <span className="text-[11px] text-neutral-500 italic">Heuristic, not mathematical proof</span>
            </div>
            <input
              type="number"
              step="0.05"
              min="0.00"
              max="1.00"
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              placeholder="0.75"
              value={confidenceScore}
              onChange={(e) => setConfidenceScore(e.target.value)}
            />
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
              {submitting ? "Synthesizing..." : "Create Draft Opportunity"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
