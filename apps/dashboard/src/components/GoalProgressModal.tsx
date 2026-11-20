import { useEffect, useState } from "react";
import { AlertCircle, LoaderCircle, TrendingDown, TrendingUp, X } from "lucide-react";
import type { GoalMetricUpdate, StrategyGoal } from "../types";

interface GoalProgressModalProps {
  isOpen: boolean;
  goal: StrategyGoal | null;
  history: GoalMetricUpdate[];
  historyLoading: boolean;
  onClose: () => void;
  onSubmit: (newValue: number, notes?: string) => Promise<void>;
}

function computeProgress(goal: StrategyGoal, currentValue: number): number {
  const { baseline_value, target_value } = goal;
  if (target_value === baseline_value) return 0;
  if (target_value > baseline_value) {
    // Increasing metric: higher is better
    const pct = ((currentValue - baseline_value) / (target_value - baseline_value)) * 100;
    return Math.max(0, Math.min(100, pct));
  } else {
    // Decreasing metric: lower is better
    const pct = ((baseline_value - currentValue) / (baseline_value - target_value)) * 100;
    return Math.max(0, Math.min(100, pct));
  }
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function GoalProgressModal({
  isOpen,
  goal,
  history,
  historyLoading,
  onClose,
  onSubmit,
}: GoalProgressModalProps) {
  const [newValue, setNewValue] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNewValue("");
      setNotes("");
      setError(null);
    }
  }, [isOpen, goal]);

  if (!isOpen || !goal) return null;

  const parsedValue = parseFloat(newValue);
  const valueValid = newValue !== "" && !isNaN(parsedValue);

  // Direction detection
  const isIncreasing = goal.target_value > goal.baseline_value;
  const isDecreasing = goal.target_value < goal.baseline_value;

  // Most recent logged value
  const latestUpdate = history.length > 0 ? history[history.length - 1] : null;
  const currentValue = latestUpdate?.new_value ?? goal.baseline_value;
  const currentProgress = computeProgress(goal, currentValue);
  const previewProgress = valueValid ? computeProgress(goal, parsedValue) : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!valueValid) { setError("Please enter a valid number."); return; }
    setSubmitting(true);
    try {
      await onSubmit(parsedValue, notes.trim() || undefined);
      setNewValue("");
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record progress.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !submitting) onClose();
  };

  const progressBarColor =
    currentProgress >= 80
      ? "var(--color-emerald, #10b981)"
      : currentProgress >= 40
      ? "var(--color-amber, #f59e0b)"
      : "var(--color-rose, #f43f5e)";

  return (
    <div className="modal-overlay" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-labelledby="goal-progress-title">
      <div className="modal-panel" style={{ maxWidth: 560 }}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> GOAL PROGRESS</div>
            <h2 id="goal-progress-title">{goal.name}</h2>
            <p className="modal-subtitle" style={{ marginTop: 2 }}>
              {goal.metric_name}
              {goal.metric_unit ? ` (${goal.metric_unit})` : ""}
              {isIncreasing && <span style={{ marginLeft: 6, color: "var(--color-emerald, #10b981)" }}><TrendingUp size={13} style={{ display: "inline", verticalAlign: "middle" }} /> Increasing metric</span>}
              {isDecreasing && <span style={{ marginLeft: 6, color: "var(--color-amber, #f59e0b)" }}><TrendingDown size={13} style={{ display: "inline", verticalAlign: "middle" }} /> Decreasing metric</span>}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} disabled={submitting} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {/* Current progress snapshot */}
        <div className="progress-snapshot panel" style={{ margin: "0 0 16px", padding: "12px 16px" }}>
          <div className="progress-snapshot-row">
            <span className="progress-label">Baseline</span>
            <span className="progress-value">{goal.baseline_value}{goal.metric_unit ? ` ${goal.metric_unit}` : ""}</span>
          </div>
          <div className="progress-snapshot-row">
            <span className="progress-label">Current</span>
            <span className="progress-value" style={{ fontWeight: 600 }}>{currentValue}{goal.metric_unit ? ` ${goal.metric_unit}` : ""}</span>
          </div>
          <div className="progress-snapshot-row">
            <span className="progress-label">Target</span>
            <span className="progress-value">{goal.target_value}{goal.metric_unit ? ` ${goal.metric_unit}` : ""}</span>
          </div>
          {/* Progress bar */}
          <div style={{ marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--color-muted, #6b7280)", marginBottom: 4 }}>
              <span>Progress</span>
              <span>{currentProgress.toFixed(1)}%</span>
            </div>
            <div style={{ height: 6, background: "rgba(255,255,255,0.08)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${currentProgress}%`, background: progressBarColor, borderRadius: 4, transition: "width 0.3s" }} />
            </div>
            {previewProgress !== null && previewProgress !== currentProgress && (
              <div style={{ marginTop: 4, fontSize: 11, color: "var(--color-muted, #6b7280)" }}>
                After check-in: <strong style={{ color: "#fff" }}>{previewProgress.toFixed(1)}%</strong>
              </div>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="modal-error" role="alert">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Log progress form */}
        <form onSubmit={(e) => void handleSubmit(e)} className="modal-form">
          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label htmlFor="goal-new-value">New metric value *</label>
              <input
                id="goal-new-value"
                type="number"
                className="form-input"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder={`e.g. ${goal.target_value}`}
                step="any"
                required
              />
            </div>
            <div className="form-group" style={{ flex: 3 }}>
              <label htmlFor="goal-notes">Notes (optional)</label>
              <input
                id="goal-notes"
                type="text"
                className="form-input"
                value={notes}
                onChange={(e) => setNotes(e.target.value.slice(0, 500))}
                placeholder="Context, source, caveats…"
                maxLength={500}
              />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || !valueValid}>
              {submitting ? <><LoaderCircle size={14} className="spin" /> Recording…</> : "Record check-in"}
            </button>
          </div>
        </form>

        {/* Metric update history */}
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: "var(--color-muted, #6b7280)", marginBottom: 8 }}>
            CHECK-IN HISTORY
          </div>
          {historyLoading ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--color-muted, #6b7280)", fontSize: 13 }}>
              <LoaderCircle size={13} className="spin" /> Loading history…
            </div>
          ) : history.length === 0 ? (
            <div style={{ color: "var(--color-muted, #6b7280)", fontSize: 13 }}>No check-ins recorded yet.</div>
          ) : (
            <div className="history-list">
              {[...history].reverse().map((update) => {
                const pct = computeProgress(goal, update.new_value);
                return (
                  <div key={update.id} className="history-item" style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontWeight: 600, fontSize: 14 }}>
                          {update.new_value}
                          {goal.metric_unit ? ` ${goal.metric_unit}` : ""}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--color-muted, #6b7280)" }}>{pct.toFixed(1)}%</span>
                      </div>
                      {update.notes && (
                        <div style={{ fontSize: 12, color: "var(--color-muted, #6b7280)", marginTop: 2 }}>{update.notes}</div>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--color-muted, #6b7280)", whiteSpace: "nowrap" }}>
                      {formatDate(update.created_at)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
