import { useState } from "react";
import { AlertCircle, ArrowRight, LoaderCircle, X } from "lucide-react";
import type { GrowthStrategy, StrategyStatus } from "../types";

interface StrategyTransitionModalProps {
  strategy: GrowthStrategy;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (targetStatus: StrategyStatus, reason?: string) => Promise<void>;
}

const ALLOWED_STRATEGY_TRANSITIONS: Record<StrategyStatus, StrategyStatus[]> = {
  draft: ["in_review", "archived"],
  in_review: ["approved", "draft", "archived"],
  approved: ["active", "draft", "archived"],
  active: ["completed", "in_review", "archived"],
  completed: ["archived"],
  archived: ["draft"],
};

const MANDATORY_REASON_TRANSITIONS: [string, string][] = [
  ["in_review", "draft"],
  ["approved", "draft"],
  ["active", "in_review"],
  ["archived", "draft"],
  ["draft", "archived"],
  ["in_review", "archived"],
  ["approved", "archived"],
  ["active", "archived"],
  ["completed", "archived"],
];

const STATUS_LABELS: Record<StrategyStatus, string> = {
  draft: "Draft",
  in_review: "Under Review",
  approved: "Approved",
  active: "Active Execution",
  completed: "Completed",
  archived: "Archived",
};

export function StrategyTransitionModal({
  strategy,
  isOpen,
  onClose,
  onSubmit,
}: StrategyTransitionModalProps) {
  const allowedTargets = ALLOWED_STRATEGY_TRANSITIONS[strategy.status] || [];
  const [selectedTarget, setSelectedTarget] = useState<StrategyStatus>(
    allowedTargets[0] || "in_review"
  );
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isMandatory = MANDATORY_REASON_TRANSITIONS.some(
    ([from, to]) => from === strategy.status && to === selectedTarget
  );

  const isValid = !isMandatory || reason.trim().length >= 10;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      setError("Please provide an explanatory justification of at least 10 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(selectedTarget, reason.trim() || undefined);
      setReason("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute transition");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal modal-compact">
        <div className="modal-header">
          <div>
            <span className="panel-kicker">STRATEGY GOVERNANCE</span>
            <h2>Lifecycle Transition</h2>
          </div>
          <button className="button-icon" onClick={onClose} disabled={submitting}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-summary">
            <span className="modal-opp-title">{strategy.name}</span>
            <div className="transition-indicator">
              <span className={`status-chip status-${strategy.status}`}>
                {STATUS_LABELS[strategy.status]}
              </span>
              <ArrowRight size={14} className="text-muted" />
              <select
                className="select-inline"
                value={selectedTarget}
                onChange={(e) => setSelectedTarget(e.target.value as StrategyStatus)}
                disabled={submitting}
              >
                {allowedTargets.map((target) => (
                  <option key={target} value={target}>
                    {STATUS_LABELS[target]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {(selectedTarget === "approved" || selectedTarget === "active") && (
            <div className="form-note">
              <strong>Requirement:</strong> Strategy approval requires all associated growth
              opportunities to be in <em>Approved</em> status.
            </div>
          )}

          <div className="form-field">
            <label>
              Transition Justification
              {isMandatory ? (
                <span className="required-mark"> * (Required, min 10 chars)</span>
              ) : (
                <span className="optional-mark"> (Optional)</span>
              )}
            </label>
            <textarea
              className="textarea-input"
              rows={3}
              placeholder={
                isMandatory
                  ? "Explain why this strategy is being reverted, paused, or archived..."
                  : "Optional review notes or decision context..."
              }
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError(null);
              }}
              disabled={submitting}
            />
            {isMandatory && (
              <span className="char-counter">
                {reason.trim().length} / 10 characters minimum
              </span>
            )}
          </div>

          {error && (
            <div className="form-error">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div className="modal-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="button button-primary"
              disabled={submitting || (isMandatory && reason.trim().length < 10)}
            >
              {submitting ? (
                <>
                  <LoaderCircle size={14} className="spin" /> Executing…
                </>
              ) : (
                "Confirm Transition"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
