import { SectionHeader } from "@/components/ui/SectionHeader";
import { JsonViewer } from "@/components/ui/JsonViewer";
import type { Incident } from "@/types/api";

interface Props {
  incident: Incident;
}

export function OverviewTab({ incident }: Props) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Main column */}
      <div className="lg:col-span-2 space-y-6">
        {/* Summary */}
        {incident.summary && (
          <div className="rounded-lg border border-[var(--color-border)] p-4">
            <SectionHeader title="Summary" />
            <p className="text-sm leading-relaxed">{incident.summary}</p>
          </div>
        )}

        {/* Raw Event */}
        {incident.raw_event && Object.keys(incident.raw_event).length > 0 && (
          <div>
            <SectionHeader title="Raw Event" />
            <JsonViewer data={incident.raw_event} />
          </div>
        )}

        {/* Metadata */}
        {Object.keys(incident.metadata).length > 0 && (
          <div>
            <SectionHeader title="Metadata" />
            <JsonViewer data={incident.metadata} />
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="space-y-6">
        {/* Source */}
        {(incident.source || incident.source_ref) && (
          <div className="rounded-lg border border-[var(--color-border)] p-4">
            <SectionHeader title="Source" />
            <div className="space-y-2 text-sm">
              {incident.source && (
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Type</span>
                  <span>{incident.source}</span>
                </div>
              )}
              {incident.source_ref && (
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">Reference</span>
                  <span className="text-right truncate max-w-[180px]" title={incident.source_ref}>
                    {incident.source_ref}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tags */}
        {incident.tags.length > 0 && (
          <div className="rounded-lg border border-[var(--color-border)] p-4">
            <SectionHeader title="Tags" />
            <div className="flex flex-wrap gap-1.5">
              {incident.tags.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 text-xs rounded-full bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="rounded-lg border border-[var(--color-border)] p-4">
          <SectionHeader title="Timestamps" />
          <div className="space-y-2 text-sm">
            {incident.detected_at && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Detected</span>
                <span>{new Date(incident.detected_at).toLocaleString()}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">Created</span>
              <span>{new Date(incident.created_at).toLocaleString()}</span>
            </div>
            {incident.resolved_at && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Resolved</span>
                <span>{new Date(incident.resolved_at).toLocaleString()}</span>
              </div>
            )}
            {incident.closed_at && (
              <div className="flex justify-between">
                <span className="text-[var(--color-text-muted)]">Closed</span>
                <span>{new Date(incident.closed_at).toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
