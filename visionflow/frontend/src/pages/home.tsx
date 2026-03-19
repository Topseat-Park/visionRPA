import { Link } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';
import type { WorkflowListItem } from '@/types/workflow';

export function HomePage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['workflows'],
    queryFn: () =>
      api.get<{ workflows: WorkflowListItem[]; total: number }>('/workflows'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/workflows/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  const handleDelete = (e: React.MouseEvent, wf: WorkflowListItem) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`"${wf.name}" 워크플로우를 삭제하시겠습니까?`)) {
      deleteMut.mutate(wf.workflow_id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">워크플로우</h2>
          <p className="text-muted-foreground">
            자동화 워크플로우를 관리합니다
          </p>
        </div>
        <Link to="/record">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            새 워크플로우
          </Button>
        </Link>
      </div>

      {isLoading && (
        <div className="text-muted-foreground">워크플로우 불러오는 중...</div>
      )}

      {data && data.workflows.length === 0 && (
        <Card className="flex flex-col items-center justify-center p-12 text-center">
          <p className="text-lg font-medium">워크플로우가 없습니다</p>
          <p className="mt-1 text-sm text-muted-foreground">
            첫 번째 워크플로우를 녹화해보세요
          </p>
          <Link to="/record" className="mt-4">
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              녹화 시작
            </Button>
          </Link>
        </Card>
      )}

      {data && data.workflows.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.workflows.map((wf) => (
            <Card
              key={wf.workflow_id}
              className="group relative cursor-pointer p-5 transition-shadow hover:shadow-md"
            >
              <Link
                to="/workflows/$workflowId"
                params={{ workflowId: wf.workflow_id }}
                className="absolute inset-0"
              />

              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1 space-y-1">
                  <h3 className="truncate font-semibold">{wf.name}</h3>
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {wf.description}
                  </p>
                </div>
                <Badge variant="secondary" className="ml-2 shrink-0">v{wf.version}</Badge>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{wf.step_count}개 스텝</span>
                  {wf.success_rate != null && (
                    <span>성공률 {Math.round(wf.success_rate * 100)}%</span>
                  )}
                </div>

                <div className="relative z-10 flex items-center gap-1">
                  <Link
                    to="/workflows/$workflowId"
                    params={{ workflowId: wf.workflow_id }}
                  >
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" title="편집">
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10 hover:text-destructive"
                    title="삭제"
                    onClick={(e) => handleDelete(e, wf)}
                    disabled={deleteMut.isPending}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
