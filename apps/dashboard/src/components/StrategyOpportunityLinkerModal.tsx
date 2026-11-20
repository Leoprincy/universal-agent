import { useEffect, useState } from "react";
import { AlertCircle, Link, LoaderCircle, X } from "lucide-react";
import { listOpportunities } from "../lib/api";
import type {
  Opportunity,
  OpportunityStatus,
  Project,
  StrategyOpportunityAssociateItem,
  StrategyStatus,
} from "../types";

interface StrategyOpportunityLinkerModalProps {
  isOpen: boolean;
  projectId: string;
  strategyId: string;
  strategyStatus: StrategyStatus;
  /** IDs already linked to this strategy — will be excluded */
  linkedOpportunityIds: Set<string>;
  projects: Project[];
  onClose: () => void;
  onSubmit: (items: StrategyOpportunityAssociateItem[]) => Promise<void>;
}

/** Statuses eligible for linking, based on strategy status */
function eligibleStatuses(strategyStatus: StrategyStatus): OpportunityStatus[] {
  if (strategyStatus === "draft") return ["in_review", "approved"];
  if (strategyStatus === "approved" || strategyStatus === "active") return ["approved"];
  return ["in_review", "approved"];
}

const STATUS_LABEL: Record<OpportunityStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  rejected: "Rejected",
  archived: "Archived",
};

const STATUS_TONE: Record<OpportunityStatus, string> = {
  draft: "neutral",
  in_review: "amber",
  approved: "emerald",
  rejected: "rose",
  archived: "neutral",
};

export function StrategyOpportunityLinkerModal({
  isOpen,
  projectId,
  strategyId,
  strategyStatus,
  linkedOpportunityIds,
  onClose,
  onSubmit,
}: StrategyOpportunityLinkerModalProps) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loadingOpps, setLoadingOpps] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [selected, setSelected] = useState<Map<string, string>>(new Map()); // oppId → rationale
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const allowed = eligibleStatuses(strategyStatus);

  useEffect(() => {
    if (!isOpen) return;
    setSelected(new Map());
    setSubmitError(null);
    setFetchError(null);

    if (!projectId) return;

    setLoadingOpps(true);
    listOpportunities(projectId)
      .then((res) => {
        // Filter to eligible statuses that are NOT already linked
        const eligible = res.items.filter(
          (opp) => allowed.includes(opp.status) && !linkedOpportunityIds.has(opp.id)
        );
        setOpportunities(eligible);
      })
      .catch((err) => {
        setFetchError(err instanceof Error ? err.message : "Failed to load opportunities.");
      })
      .finally(() => setLoadingOpps(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, projectId, strategyId, strategyStatus]);

  if (!isOpen) return null;

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(id)) next.delete(id);
      else next.set(id, "");
      return next;
    });
  };

  const setRationale = (id: string, rationale: string) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(id)) next.set(id, rationale.slice(0, 500));
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (selected.size === 0) {
      setSubmitError("Select at least one opportunity to link.");
      return;
    }

    const items: StrategyOpportunityAssociateItem[] = Array.from(selected.entries()).map(
      ([opportunity_id, strategic_rationale]) => ({
        opportunity_id,
        strategic_rationale: strategic_rationale.trim() || undefined,
      })
    );

    setSubmitting(true);
    try {
      await onSubmit(items);
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to link opportunities.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !submitting) onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-labelledby="opp-linker-title">
      <div className="modal-panel" style={{ maxWidth: 600 }}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> LINK OPPORTUNITIES</div>
            <h2 id="opp-linker-title">Link opportunities to strategy</h2>
            <p className="modal-subtitle" style={{ marginTop: 2 }}>
              Eligible statuses for a <strong>{strategyStatus}</strong> strategy:{" "}
              {allowed.map((s) => STATUS_LABEL[s]).join(", ")}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} disabled={submitting} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {/* Errors */}
        {(fetchError ?? submitError) && (
          <div className="modal-error" role="alert">
            <AlertCircle size={14} />
            <span>{fetchError ?? submitError}</span>
          </div>
        )}

        {/* Opportunity list */}
        <form onSubmit={(e) => void handleSubmit(e)} className="modal-form">
          {loadingOpps ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--color-muted, #6b7280)", padding: "16px 0" }}>
              <LoaderCircle size={14} className="spin" /> Loading opportunities…
            </div>
          ) : opportunities.length === 0 ? (
            <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13, padding: "12px 0" }}>
              No eligible opportunities available.
              {allowed.length > 0 && ` Opportunities must be ${allowed.map((s) => STATUS_LABEL[s]).join(" or ")}.`}
            </div>
          ) : (
            <div className="opp-linker-list" style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 360, overflowY: "auto" }}>
              {opportunities.map((opp) => {
                const isSelected = selected.has(opp.id);
                return (
                  <div
                    key={opp.id}
                    className={`opp-linker-item panel ${isSelected ? "selected" : ""}`}
                    style={{
                      padding: "10px 12px",
                      border: `1px solid ${isSelected ? "rgba(99,102,241,0.6)" : "rgba(255,255,255,0.08)"}`,
                      borderRadius: 8,
                      cursor: "pointer",
                      transition: "border-color 0.15s",
                    }}
                    onClick={() => toggleSelect(opp.id)}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(opp.id)}
                        onClick={(e) => e.stopPropagation()}
                        style={{ marginTop: 2, flexShrink: 0 }}
                        aria-label={`Select ${opp.title}`}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                          <span style={{ fontWeight: 600, fontSize: 13 }}>{opp.title}</span>
                          <span className={`status-badge ${STATUS_TONE[opp.status]}`} style={{ fontSize: 10 }}>
                            <span className="status-dot" />{STATUS_LABEL[opp.status]}
                          </span>
                        </div>
                        {opp.problem_statement && (
                          <div style={{ fontSize: 12, color: "var(--color-muted, #6b7280)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {opp.problem_statement}
                          </div>
                        )}
                      </div>
                    </div>
                    {isSelected && (
                      <div style={{ marginTop: 8 }} onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          className="form-input"
                          value={selected.get(opp.id) ?? ""}
                          onChange={(e) => setRationale(opp.id, e.target.value)}
                          placeholder="Strategic rationale (optional)"
                          maxLength={500}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="modal-actions" style={{ marginTop: 16 }}>
            <span style={{ fontSize: 12, color: "var(--color-muted, #6b7280)" }}>
              {selected.size > 0 ? `${selected.size} selected` : ""}
            </span>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || selected.size === 0}>
              {submitting ? (
                <><LoaderCircle size={14} className="spin" /> Linking…</>
              ) : (
                <><Link size={14} /> Link {selected.size > 0 ? `${selected.size} ` : ""}opportunity</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
