import { useEffect, useState } from "react";
import { AlertCircle, Link, X } from "lucide-react";
import { associateResearch, listResearchRecords } from "../lib/api";
import type { Opportunity, ResearchRecord } from "../types";

interface EvidenceLinkerModalProps {
  opportunity: Opportunity;
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onLinked: () => void;
}

export function EvidenceLinkerModal({
  opportunity,
  projectId,
  isOpen,
  onClose,
  onLinked,
}: EvidenceLinkerModalProps) {
  const [records, setRecords] = useState<ResearchRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    listResearchRecords(projectId, { limit: 100 })
      .then((res) => {
        setRecords(res.items);
        if (res.items.length > 0) {
          setSelectedId(res.items[0].id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load research records"))
      .finally(() => setLoading(false));
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) {
      setError("Please select a research record to link.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await associateResearch(projectId, opportunity.id, [
        { research_id: selectedId, notes: notes.trim() || undefined },
      ]);
      onLinked();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to associate research record");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-card max-w-lg w-full">
        <div className="modal-header">
          <div className="flex items-center gap-2">
            <Link size={18} className="text-violet-400" />
            <div>
              <h3 className="text-base font-bold text-white">Attach Evidence to Opportunity</h3>
              <p className="text-xs text-neutral-400">
                Link verifiable research to <strong>{opportunity.title}</strong>
              </p>
            </div>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-4">
          {error && (
            <div className="flex items-center gap-2 text-rose-400 text-xs bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20">
              <AlertCircle size={14} />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Select Research Record *
            </label>
            {loading ? (
              <div className="text-xs text-neutral-400 p-3 bg-white/5 rounded-lg">Loading evidence records...</div>
            ) : records.length === 0 ? (
              <div className="text-xs text-neutral-400 p-3 bg-white/5 rounded-lg border border-dashed border-white/10">
                No research records exist in this project yet. Create one in the Research Vault first.
              </div>
            ) : (
              <select
                className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
              >
                {records.map((r) => (
                  <option key={r.id} value={r.id} className="bg-neutral-900 text-white">
                    [{r.source_type}] {r.title}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-neutral-300 mb-1">
              Association Notes <span className="text-neutral-500">(Optional)</span>
            </label>
            <textarea
              className="w-full bg-white/5 border border-white/15 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-violet-500"
              rows={3}
              placeholder="Explain how this specific observation or data point supports the hypothesis..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

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
              disabled={!selectedId || submitting}
            >
              {submitting ? "Linking..." : "Attach Evidence"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
