import { useParams } from '@tanstack/react-router';

export function WorkflowEditPage() {
  const { workflowId } = useParams({ strict: false });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight">Edit Workflow</h2>
      <p className="text-muted-foreground">
        Workflow: {workflowId} — Step editor will be added in Phase 2.
      </p>
    </div>
  );
}
