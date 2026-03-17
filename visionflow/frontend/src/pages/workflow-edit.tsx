import { useState } from 'react';
import { useParams, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Play, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';
import type { Workflow } from '@/types/workflow';

const STEP_TYPE_LABELS: Record<string, string> = {
  vision_click: 'Click',
  clipboard_paste: 'Type',
  hotkey: 'Hotkey',
  scroll: 'Scroll',
  drag: 'Drag',
  cmd: 'Command',
  navigate: 'Navigate',
  wait: 'Wait',
};

const STEP_TYPE_COLORS: Record<string, string> = {
  vision_click: 'bg-blue-100 text-blue-800',
  clipboard_paste: 'bg-green-100 text-green-800',
  hotkey: 'bg-purple-100 text-purple-800',
  scroll: 'bg-yellow-100 text-yellow-800',
  drag: 'bg-orange-100 text-orange-800',
  cmd: 'bg-red-100 text-red-800',
  navigate: 'bg-cyan-100 text-cyan-800',
  wait: 'bg-gray-100 text-gray-800',
};

export function WorkflowEditPage() {
  const { workflowId } = useParams({ strict: false });
  const navigate = useNavigate();
  const [runError, setRunError] = useState<string | null>(null);

  const { data: workflow, isLoading, error } = useQuery<Workflow>({
    queryKey: ['workflow', workflowId],
    queryFn: () => api.get<Workflow>(`/workflows/${workflowId}`),
    enabled: !!workflowId,
  });

  const runMut = useMutation({
    mutationFn: () =>
      api.post<{ run_id: string }>(`/runs?workflow_id=${workflowId}`, {}),
    onSuccess: (run) => {
      navigate({ to: '/runs/$runId', params: { runId: run.run_id } });
    },
    onError: (e: Error) => setRunError(e.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Workflow not found</h2>
        <Button variant="outline" onClick={() => navigate({ to: '/' })}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{workflow.name}</h2>
          <p className="text-muted-foreground">{workflow.description}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {workflow.steps.length} steps · v{workflow.version}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => runMut.mutate()}
            disabled={runMut.isPending || workflow.steps.length === 0}
          >
            <Play className="mr-2 h-4 w-4" />
            {runMut.isPending ? 'Starting...' : 'Run'}
          </Button>
        </div>
      </div>

      {runError && <p className="text-sm text-destructive">{runError}</p>}

      {workflow.steps.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          No steps recorded. Record a workflow first.
        </Card>
      ) : (
        <div className="space-y-2">
          {workflow.steps.map((step, idx) => (
            <Card key={step.id} className="flex items-center gap-4 p-4">
              <span className="w-8 text-center text-sm font-semibold text-muted-foreground">
                {idx + 1}
              </span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-medium ${STEP_TYPE_COLORS[step.type] ?? 'bg-muted text-muted-foreground'}`}
              >
                {STEP_TYPE_LABELS[step.type] ?? step.type}
              </span>
              <span className="flex-1 text-sm">{step.description}</span>
              {step.on_failure !== 'human' && (
                <Badge variant="outline" className="text-xs">
                  {step.on_failure}
                </Badge>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
