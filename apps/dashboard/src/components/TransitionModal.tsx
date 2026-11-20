import { useState } from "react";
import { AlertCircle, ArrowRight, X } from "lucide-react";
import type { Opportunity, OpportunityStatus } from "../types";

interface TransitionModalProps {
  opportunity: Opportunity;
  targetStatus: OpportunityStatus;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (targetStatus: OpportunityStatus, reason?: string) => Promise<void>;
}

const MANDATORY_REASON_TRANSITIONS: [string, string][] = [
  ["in_review", "rejected"],
  ["in_review", "draft"],
  ["rejected", "draft"],
];

export function TransitionModal({
  opportunity,
  targetStatus,
  isOpen,
  onClose,
  onSubmit,
}: TransitionModalProps) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isMandatory = MANDATORY_REASON_TRANSITIONS.some(
    ([from, to]) => from === opportunity.status && to === targetStatus
  );

  const isValid = !isMandatory || reason.trim().length >= 10;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) {
      setError("Please provide an explanatory reason of at least 10 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(targetStatus, reason.trim() || undefined);
      setReason("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to transition status");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card max-w-md w-full">
        <div className="modal-header">
          <div>
            <h3 className="text-lg font-bold">Lifecycle State Transition</h3>
            <p className="text-xs text-neutral-400 mt-1">
              Transitioning <strong>{opportunity.title}</strong>
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10 text-sm">
            <span className="badge">{opportunity.status}</span>
            <ArrowRight size={16} className="text-neutral-400" />
            <span className="badge badge-active">{targetStatus}</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Reason / Review Notes {isMandatory ? <span className="text-rose-400">*</span> : <span className="text-neutral-500">(Optional)</span>}
            </label>
            <textarea
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:border-violet-500"
              rows={3}
              placeholder={
                isMandatory
                  ? "Required: explain why this opportunity is being rejected or returned to draft (min 10 chars)..."
                  : "Optional notes for the immutable audit history..."
              }
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (error) setError(null);
              }}
            />
            {isMandatory && (
              <span className={`text-[11px] block mt-1 ${reason.trim().length >= 10 ? "text-emerald-400" : "text-neutral-400"}`}>
                {reason.trim().length}/10 characters required
              </span>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-rose-400 text-xs bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
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
              disabled={!isValid || submitting}
            >
              {submitting ? "Transitioning..." : "Confirm Transition"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
