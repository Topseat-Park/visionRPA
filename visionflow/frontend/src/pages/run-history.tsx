import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Ban,
  History,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';
import type { RunMeta } from '@/types/run';

type StatusFilter = 'all' | 'completed' | 'failed' | 'running' | 'aborted';

const STATUS_FILTERS: { label: string; value: StatusFilter }[] = [
  { label: '전체', value: 'all' },
  { label: '완료', value: 'completed' },
  { label: '실패', value: 'failed' },
  { label: '실행 중', value: 'running' },
  { label: '중단', value: 'aborted' },
];

function statusIcon(status: RunMeta['status']) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case 'failed':
      return <XCircle className="h-5 w-5 text-red-500" />;
    case 'running':
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    case 'pending':
      return <Clock className="h-5 w-5 text-yellow-500" />;
    case 'aborted':
      return <Ban className="h-5 w-5 text-muted-foreground" />;
  }
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return 'running...';

  const start = new Date(startedAt).getTime();
  const end = new Date(finishedAt).getTime();
  const diffMs = end - start;

  if (diffMs < 0) return '--';

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function statusBadgeVariant(
  status: RunMeta['status']
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
      return 'default';
    case 'failed':
      return 'destructive';
    case 'running':
      return 'secondary';
    case 'pending':
      return 'outline';
    case 'aborted':
      return 'outline';
  }
}

export function RunHistoryPage() {
  const [filter, setFilter] = useState<StatusFilter>('all');

  const { data: runs, isLoading } = useQuery({
    queryKey: ['runs', filter],
    queryFn: () =>
      api.get<RunMeta[]>(
        filter === 'all' ? '/runs' : `/runs?status=${filter}`
      ),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <History className="h-6 w-6" />
          <h2 className="text-2xl font-bold tracking-tight">Run History</h2>
        </div>
        <p className="mt-1 text-muted-foreground">
          View execution history across all workflows
        </p>
      </div>

      {/* Status filter bar */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <Button
            key={f.value}
            variant={filter === f.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Empty state */}
      {runs && runs.length === 0 && (
        <Card className="flex flex-col items-center justify-center p-12 text-center">
          <History className="h-10 w-10 text-muted-foreground" />
          <p className="mt-4 text-lg font-medium">No runs yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Execute a workflow to see history here.
          </p>
        </Card>
      )}

      {/* Run list */}
      {runs && runs.length > 0 && (
        <div className="grid gap-3">
          {runs.map((run) => (
            <Link key={run.run_id} to="/runs/$runId" params={{ runId: run.run_id }}>
              <Card className="cursor-pointer p-4 transition-shadow hover:shadow-md">
                <div className="flex items-start gap-4">
                  {/* Status icon */}
                  <div className="mt-0.5 shrink-0">{statusIcon(run.status)}</div>

                  {/* Main content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold truncate">
                        {run.workflow_name}
                      </span>
                      <Badge variant={statusBadgeVariant(run.status)}>
                        {run.status}
                      </Badge>
                    </div>

                    <p className="mt-0.5 text-xs text-muted-foreground truncate">
                      {run.run_id}
                    </p>

                    {/* Meta row */}
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>
                        Started{' '}
                        {new Date(run.started_at).toLocaleString()}
                      </span>
                      <span>
                        Duration: {formatDuration(run.started_at, run.finished_at)}
                      </span>
                      <span>
                        Step {run.current_step} / {run.total_steps}
                      </span>
                    </div>

                    {/* Error message */}
                    {run.error && (
                      <p className="mt-2 text-xs text-destructive truncate">
                        {run.error}
                      </p>
                    )}
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
