import { useEffect, useState } from "react";
import { AlertCircle, LoaderCircle, X } from "lucide-react";
import type { StrategyGoal, StrategyGoalCreateInput, StrategyGoalUpdateInput } from "../types";

interface GoalEditorModalProps {
  isOpen: boolean;
  /** When provided, the modal is in edit mode; otherwise create mode. */
  goal?: StrategyGoal | null;
  strategyId: string;
  onClose: () => void;
  onSubmit: (data: StrategyGoalCreateInput | StrategyGoalUpdateInput) => Promise<void>;
}

function clamp(val: string): string {
  return val.trim().slice(0, 500);
}

export function GoalEditorModal({
  isOpen,
  goal,
  onClose,
  onSubmit,
}: GoalEditorModalProps) {
  const isEdit = !!goal;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [metricName, setMetricName] = useState("");
  const [metricUnit, setMetricUnit] = useState("");
  const [baselineValue, setBaselineValue] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [deadline, setDeadline] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Populate fields when editing
  useEffect(() => {
    if (isOpen) {
      if (goal) {
        setName(goal.name);
        setDescription(goal.description ?? "");
        setMetricName(goal.metric_name);
        setMetricUnit(goal.metric_unit ?? "");
        setBaselineValue(String(goal.baseline_value));
        setTargetValue(String(goal.target_value));
        setDeadline(goal.deadline ? goal.deadline.slice(0, 10) : "");
      } else {
        setName("");
        setDescription("");
        setMetricName("");
        setMetricUnit("");
        setBaselineValue("");
        setTargetValue("");
        setDeadline("");
      }
      setError(null);
    }
  }, [isOpen, goal]);

  if (!isOpen) return null;

  const baseNum = parseFloat(baselineValue);
  const targetNum = parseFloat(targetValue);
  const baseValid = baselineValue !== "" && !isNaN(baseNum);
  const targetValid = targetValue !== "" && !isNaN(targetNum);
  const sameValues = baseValid && targetValid && baseNum === targetNum;

  const directionHint =
    baseValid && targetValid && !sameValues
      ? targetNum > baseNum
        ? "↑ Increasing metric (higher is better)"
        : "↓ Decreasing metric (lower is better, e.g. churn, latency)"
      : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) { setError("Goal name is required."); return; }
    if (!metricName.trim()) { setError("Metric name is required."); return; }
    if (!baseValid) { setError("Baseline value must be a number."); return; }
    if (!targetValid) { setError("Target value must be a number."); return; }
    if (sameValues) { setError("Baseline and target values must differ."); return; }

    setSubmitting(true);
    try {
      const payload: StrategyGoalCreateInput = {
        name: name.trim(),
        description: description.trim() || undefined,
        metric_name: metricName.trim(),
        metric_unit: metricUnit.trim(),
        baseline_value: baseNum,
        target_value: targetNum,
        deadline: deadline || undefined,
      };
      await onSubmit(payload);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save goal.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && !submitting) onClose();
  };

  return (
    <div className="modal-overlay" onClick={handleBackdrop} role="dialog" aria-modal="true" aria-labelledby="goal-editor-title">
      <div className="modal-panel" style={{ maxWidth: 520 }}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> GOAL</div>
            <h2 id="goal-editor-title">{isEdit ? "Edit goal" : "New goal"}</h2>
          </div>
          <button className="icon-button" onClick={onClose} disabled={submitting} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="modal-error" role="alert">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={(e) => void handleSubmit(e)} className="modal-form">
          <div className="form-group">
            <label htmlFor="goal-name">Goal name *</label>
            <input
              id="goal-name"
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(clamp(e.target.value))}
              placeholder="e.g. Grow monthly active users to 50 k"
              maxLength={200}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="goal-description">Description</label>
            <textarea
              id="goal-description"
              className="form-input"
              value={description}
              onChange={(e) => setDescription(clamp(e.target.value))}
              placeholder="Describe what achieving this goal means for the business"
              rows={3}
              maxLength={500}
            />
          </div>

          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label htmlFor="goal-metric-name">Metric name *</label>
              <input
                id="goal-metric-name"
                type="text"
                className="form-input"
                value={metricName}
                onChange={(e) => setMetricName(clamp(e.target.value))}
                placeholder="e.g. Monthly Active Users"
                maxLength={120}
                required
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="goal-metric-unit">Unit</label>
              <input
                id="goal-metric-unit"
                type="text"
                className="form-input"
                value={metricUnit}
                onChange={(e) => setMetricUnit(clamp(e.target.value))}
                placeholder="users, %, ms…"
                maxLength={40}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="goal-baseline">Baseline value *</label>
              <input
                id="goal-baseline"
                type="number"
                className="form-input"
                value={baselineValue}
                onChange={(e) => setBaselineValue(e.target.value)}
                placeholder="Current / starting value"
                step="any"
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="goal-target">Target value *</label>
              <input
                id="goal-target"
                type="number"
                className="form-input"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                placeholder="Goal value to reach"
                step="any"
              />
            </div>
          </div>

          {directionHint && (
            <div className="form-hint" style={{ marginTop: -8 }}>{directionHint}</div>
          )}

          <div className="form-group">
            <label htmlFor="goal-deadline">Deadline</label>
            <input
              id="goal-deadline"
              type="date"
              className="form-input"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? <><LoaderCircle size={14} className="spin" /> Saving…</> : isEdit ? "Save changes" : "Create goal"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
