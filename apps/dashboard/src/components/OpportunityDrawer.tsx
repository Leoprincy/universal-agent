import { useEffect, useState } from "react";
import {
  AlertCircle,
  History,
  Link,
  Plus,
  Sparkles,
  Tag,
  Unlink,
  User,
  X,
} from "lucide-react";
import {
  getOpportunityHistory,
  listAssociatedResearch,
  unlinkResearch,
} from "../lib/api";
import type {
  AssociatedResearch,
  Opportunity,
  OpportunityPriority,
  OpportunityStatus,
  OpportunityStatusHistory,
} from "../types";
import { TransitionModal } from "./TransitionModal";

interface OpportunityDrawerProps {
  opportunity: Opportunity | null;
  projectId: string;
  onClose: () => void;
  onOpportunityUpdated: (opp: Opportunity) => void;
  onOpenLinker: () => void;
  onTransition: (opp: Opportunity, targetStatus: OpportunityStatus, reason?: string) => Promise<Opportunity>;
}

const ALLOWED_TARGETS: Record<OpportunityStatus, OpportunityStatus[]> = {
  draft: ["in_review", "archived"],
  in_review: ["approved", "rejected", "draft", "archived"],
  approved: ["archived"],
  rejected: ["draft", "archived"],
  archived: [],
};

export function OpportunityDrawer({
  opportunity,
  projectId,
  onClose,
  onOpportunityUpdated,
  onOpenLinker,
  onTransition,
}: OpportunityDrawerProps) {
  const [history, setHistory] = useState<OpportunityStatusHistory[]>([]);
  const [linkedResearch, setLinkedResearch] = useState<AssociatedResearch[]>([]);
  const [loadingLinks, setLoadingLinks] = useState(false);
  const [pendingTarget, setPendingTarget] = useState<OpportunityStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!opportunity) return;
    let mounted = true;
    setLoadingLinks(true);

    Promise.allSettled([
      getOpportunityHistory(projectId, opportunity.id),
      listAssociatedResearch(projectId, opportunity.id),
    ]).then(([histRes, linksRes]) => {
      if (!mounted) return;
      if (histRes.status === "fulfilled") {
        setHistory(histRes.value.items);
      }
      if (linksRes.status === "fulfilled") {
        setLinkedResearch(linksRes.value);
      }
      setLoadingLinks(false);
    });

    return () => {
      mounted = false;
    };
  }, [opportunity, projectId]);

  if (!opportunity) return null;

  const validTargets = ALLOWED_TARGETS[opportunity.status] || [];

  const handleExecuteTransition = async (target: OpportunityStatus, reason?: string) => {
    const updated = await onTransition(opportunity, target, reason);
    onOpportunityUpdated(updated);
    // Refresh history
    const hist = await getOpportunityHistory(projectId, opportunity.id);
    setHistory(hist.items);
  };

  const handleUnlink = async (researchId: string) => {
    try {
      await unlinkResearch(projectId, opportunity.id, researchId);
      setLinkedResearch((prev) => prev.filter((item) => item.research_id !== researchId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlink evidence");
    }
  };

  const getPriorityBadge = (p: OpportunityPriority) => {
    switch (p) {
      case "p0_urgent":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">P0 • Critical (Quick Win)</span>;
      case "p1_high":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">P1 • High Impact</span>;
      case "p2_medium":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">P2 • Medium</span>;
      case "p3_low":
        return <span className="px-2 py-0.5 rounded text-xs font-semibold bg-neutral-500/20 text-neutral-300 border border-neutral-500/30">P3 • Low</span>;
    }
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-40 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed top-0 right-0 bottom-0 w-full max-w-2xl bg-canvas-elevated border-l border-white/10 z-50 overflow-y-auto flex flex-col">
        {/* Drawer Header */}
        <div className="p-6 border-b border-white/10 flex items-start justify-between bg-surface/50 sticky top-0 backdrop-blur-md z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="badge badge-active">{opportunity.category}</span>
              <span className="badge">{opportunity.status}</span>
              {getPriorityBadge(opportunity.priority)}
            </div>
            <h2 className="text-xl font-bold text-white">{opportunity.title}</h2>
            <div className="text-xs text-neutral-400 mt-1 flex items-center gap-3">
              <span>Slug: <code className="text-violet-300">{opportunity.slug}</code></span>
              <span>Created {new Date(opportunity.created_at).toLocaleDateString()}</span>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="m-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-300 text-xs">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        <div className="p-6 flex flex-col gap-6 flex-1">
          {/* Lifecycle Action Bar */}
          <div className="p-4 rounded-xl bg-white/5 border border-white/10 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-neutral-300">LIFECYCLE STATE ACTIONS</span>
              <span className="text-xs text-neutral-400">Current status: <strong className="text-white capitalize">{opportunity.status.replace("_", " ")}</strong></span>
            </div>
            <div className="flex flex-wrap gap-2">
              {validTargets.length === 0 ? (
                <span className="text-xs text-neutral-500 italic">No further transitions permitted (terminal state).</span>
              ) : (
                validTargets.map((target) => (
                  <button
                    key={target}
                    className="button button-secondary text-xs"
                    onClick={() => setPendingTarget(target)}
                  >
                    Transition to {target.replace("_", " ")}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* 4-Part Structured Domain Taxonomy */}
          <div className="grid grid-cols-1 gap-4">
            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <AlertCircle size={13} /> 1. Problem Statement
              </div>
              <p className="text-sm text-neutral-200 leading-relaxed">{opportunity.problem_statement}</p>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Sparkles size={13} /> 2. Falsifiable Hypothesis
              </div>
              <p className="text-sm text-neutral-200 leading-relaxed font-mono text-xs bg-black/30 p-2.5 rounded border border-white/5">
                {opportunity.hypothesis}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <Tag size={13} /> 3. Proposed Mechanism
              </div>
              <p className="text-sm text-neutral-200 leading-relaxed">{opportunity.proposed_mechanism}</p>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                <User size={13} /> 4. Target Audience
              </div>
              <p className="text-sm text-neutral-200 leading-relaxed">{opportunity.target_audience}</p>
            </div>
          </div>

          {/* Impact, Effort & Confidence Metadata */}
          <div className="grid grid-cols-3 gap-3 p-4 rounded-xl bg-white/5 border border-white/10 text-center">
            <div>
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider block">Impact</span>
              <strong className="text-sm text-white capitalize">{opportunity.estimated_impact}</strong>
            </div>
            <div>
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider block">Effort</span>
              <strong className="text-sm text-white capitalize">{opportunity.estimated_effort}</strong>
            </div>
            <div>
              <span className="text-[10px] text-neutral-400 uppercase tracking-wider block">Confidence Score</span>
              <strong className="text-sm text-violet-300">
                {opportunity.confidence_score !== null && opportunity.confidence_score !== undefined
                  ? `${(opportunity.confidence_score * 100).toFixed(0)}%`
                  : "Unscored"}
              </strong>
            </div>
          </div>

          {/* Evidence / Research Association Section */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Link size={16} className="text-violet-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Supporting Evidence ({linkedResearch.length})
                </h3>
              </div>
              <button className="button button-quiet text-xs" onClick={onOpenLinker}>
                <Plus size={14} /> Link Evidence
              </button>
            </div>

            {loadingLinks ? (
              <div className="p-4 text-center text-xs text-neutral-400">Loading evidence...</div>
            ) : linkedResearch.length === 0 ? (
              <div className="p-6 text-center rounded-xl border border-dashed border-white/15 bg-white/[0.02]">
                <p className="text-xs text-neutral-400 mb-2">No research records linked yet.</p>
                <button className="button button-secondary text-xs" onClick={onOpenLinker}>
                  Attach Evidence from Vault
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {linkedResearch.map((item) => (
                  <div
                    key={item.research_id}
                    className="p-3 rounded-lg bg-white/5 border border-white/10 flex items-start justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge text-[10px]">{item.research?.source_type ?? "evidence"}</span>
                        <strong className="text-white text-xs">{item.research?.title ?? item.research_id}</strong>
                      </div>
                      {item.notes && (
                        <p className="text-neutral-300 mt-1 italic">
                          "{item.notes}"
                        </p>
                      )}
                      {item.research?.source_quote && (
                        <blockquote className="border-l-2 border-violet-500/50 pl-2 text-neutral-400 mt-1 text-[11px]">
                          {item.research.source_quote}
                        </blockquote>
                      )}
                    </div>
                    <button
                      className="icon-button text-neutral-400 hover:text-rose-400"
                      onClick={() => handleUnlink(item.research_id)}
                      title="Unlink evidence"
                    >
                      <Unlink size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Immutable Audit History Timeline */}
          <div className="flex flex-col gap-3 pt-4 border-t border-white/10">
            <div className="flex items-center gap-2">
              <History size={16} className="text-neutral-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Immutable Status History ({history.length})
              </h3>
            </div>

            <div className="flex flex-col gap-3 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-white/10 pl-6">
              {history.map((entry) => (
                <div key={entry.id} className="relative flex flex-col gap-1 text-xs">
                  <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-violet-500 ring-4 ring-canvas" />
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white capitalize">
                      {entry.previous_status ? `${entry.previous_status} → ${entry.new_status}` : `Created as ${entry.new_status}`}
                    </span>
                    <span className="text-[11px] text-neutral-400">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-neutral-400 text-[11px] flex items-center gap-2">
                    <span>Actor: <code className="text-neutral-300 font-mono">Workspace ({entry.actor})</code></span>
                  </div>
                  {entry.reason && (
                    <div className="p-2 rounded bg-white/5 border border-white/5 text-neutral-300 mt-0.5 text-xs">
                      {entry.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {pendingTarget && (
        <TransitionModal
          opportunity={opportunity}
          targetStatus={pendingTarget}
          isOpen={Boolean(pendingTarget)}
          onClose={() => setPendingTarget(null)}
          onSubmit={async (status, reason) => {
            await handleExecuteTransition(status, reason);
            setPendingTarget(null);
          }}
        />
      )}
    </>
  );
}
