import { useParams } from '@tanstack/react-router';

export function RunMonitorPage() {
  const { runId } = useParams({ strict: false });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Run Monitor</h2>
      <p className="text-muted-foreground">
        Run: {runId} — Real-time monitoring will be added in Phase 3.
      </p>
    </div>
  );
}
