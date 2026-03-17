import { useParams, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Square, ArrowLeft, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';

interface RunMeta {
  run_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'aborted';
  started_at: string;
  finished_at: string | null;
  current_step: number;
  total_steps: number;
  error: string | null;
}

const STATUS_CONFIG: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  pending: { label: 'Pending', variant: 'secondary' },
  running: { label: 'Running', variant: 'default' },
  completed: { label: 'Completed', variant: 'outline' },
  failed: { label: 'Failed', variant: 'destructive' },
  aborted: { label: 'Aborted', variant: 'destructive' },
};

export function RunMonitorPage() {
  const { runId } = useParams({ strict: false });
  const navigate = useNavigate();

  const { data: run, isLoading } = useQuery<RunMeta>({
    queryKey: ['run', runId],
    queryFn: () => api.get<RunMeta>(`/runs/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'pending' ? 1000 : false;
    },
  });

  const abortMut = useMutation({
    mutationFn: () => api.post(`/runs/${runId}/abort`, {}),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Run not found</h2>
        <Button variant="outline" onClick={() => navigate({ to: '/runs' })}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
      </div>
    );
  }

  const cfg = STATUS_CONFIG[run.status] ?? { label: run.status, variant: 'outline' as const };
  const progress = run.total_steps > 0 ? (run.current_step / run.total_steps) * 100 : 0;
  const isActive = run.status === 'running' || run.status === 'pending';

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Run Monitor</h2>
          <p className="text-sm text-muted-foreground">
            {run.workflow_name} — {run.run_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={cfg.variant}>{cfg.label}</Badge>
          {isActive && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => abortMut.mutate()}
              disabled={abortMut.isPending}
            >
              <Square className="mr-1 h-3 w-3" /> Abort
            </Button>
          )}
        </div>
      </div>

      <Card className="p-6 space-y-4">
        {/* Progress bar */}
        <div>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-muted-foreground">
              Step {run.current_step} / {run.total_steps}
            </span>
            <span className="font-medium">{Math.round(progress)}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Current step */}
        {isActive && (
          <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="text-sm">
              {run.current_step > 0
                ? `Executing step ${run.current_step}...`
                : 'Starting replay...'}
            </span>
          </div>
        )}

        {/* Completed */}
        {run.status === 'completed' && (
          <div className="flex items-center gap-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Replay completed successfully</span>
          </div>
        )}

        {/* Failed / aborted */}
        {(run.status === 'failed' || run.status === 'aborted') && (
          <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-red-800">
            <XCircle className="h-4 w-4" />
            <span className="text-sm font-medium">
              {run.status === 'aborted' ? 'Run aborted' : `Failed: ${run.error ?? 'Unknown error'}`}
            </span>
          </div>
        )}

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-2 border-t pt-4 text-sm">
          <span className="text-muted-foreground">Started</span>
          <span>{new Date(run.started_at).toLocaleString()}</span>
          {run.finished_at && (
            <>
              <span className="text-muted-foreground">Finished</span>
              <span>{new Date(run.finished_at).toLocaleString()}</span>
            </>
          )}
        </div>
      </Card>

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() => navigate({ to: '/workflows/$workflowId', params: { workflowId: run.workflow_id } })}
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Workflow
        </Button>
      </div>
    </div>
  );
}
