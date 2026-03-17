import { Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';
import type { WorkflowListItem } from '@/types/workflow';

export function HomePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['workflows'],
    queryFn: () =>
      api.get<{ workflows: WorkflowListItem[]; total: number }>('/workflows'),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Workflows</h2>
          <p className="text-muted-foreground">
            Manage your automated workflows
          </p>
        </div>
        <Link to="/record">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Workflow
          </Button>
        </Link>
      </div>

      {isLoading && (
        <div className="text-muted-foreground">Loading workflows...</div>
      )}

      {data && data.workflows.length === 0 && (
        <Card className="flex flex-col items-center justify-center p-12 text-center">
          <p className="text-lg font-medium">No workflows yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Record your first workflow to get started
          </p>
          <Link to="/record" className="mt-4">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Start Recording
            </Button>
          </Link>
        </Card>
      )}

      {data && data.workflows.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.workflows.map((wf) => (
            <Link
              key={wf.workflow_id}
              to="/workflows/$workflowId"
              params={{ workflowId: wf.workflow_id }}
            >
              <Card className="cursor-pointer p-5 transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <h3 className="font-semibold">{wf.name}</h3>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {wf.description}
                    </p>
                  </div>
                  <Badge variant="secondary">v{wf.version}</Badge>
                </div>
                <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{wf.step_count} steps</span>
                  {wf.success_rate != null && (
                    <span>{Math.round(wf.success_rate * 100)}% success</span>
                  )}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
