import { useParams, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Square,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Loader2,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Eye,
  Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api-client';
import type { RunMeta, DryrunStepResult } from '@/types/run';

const POLLING_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

const STATUS_CONFIG: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  pending: { label: 'Pending', variant: 'secondary' },
  running: { label: 'Running', variant: 'default' },
  completed: { label: 'Completed', variant: 'outline' },
  failed: { label: 'Failed', variant: 'destructive' },
  aborted: { label: 'Aborted', variant: 'destructive' },
};

const METHOD_LABELS: Record<string, string> = {
  ai: 'AI 비전',
  template: 'OpenCV 템플릿',
  fallback: '좌표 폴백',
};

export function RunMonitorPage() {
  const { runId } = useParams({ strict: false });
  const navigate = useNavigate();

  const { data: run, isLoading } = useQuery<RunMeta>({
    queryKey: ['run', runId],
    queryFn: () => api.get<RunMeta>(`/runs/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const status = data.status;
      if (status !== 'running' && status !== 'pending') return false;
      // Stop polling after 10 minutes to prevent infinite loop
      const elapsed = Date.now() - new Date(data.started_at).getTime();
      if (elapsed > POLLING_TIMEOUT_MS) return false;
      return 1000;
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
  const isTimedOut =
    isActive && Date.now() - new Date(run.started_at).getTime() > POLLING_TIMEOUT_MS;
  const isDryrun = run.mode === 'dryrun';

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
          {isDryrun && (
            <Badge variant="secondary" className="gap-1">
              <Eye className="h-3 w-3" />
              드라이런
            </Badge>
          )}
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
                ? isDryrun
                  ? `스텝 ${run.current_step} 검증 중...`
                  : `Executing step ${run.current_step}...`
                : isDryrun
                  ? '드라이런 시작 중...'
                  : 'Starting replay...'}
            </span>
          </div>
        )}

        {/* Timed out warning */}
        {isTimedOut && (
          <div className="flex items-center gap-2 rounded-md bg-yellow-50 p-3 text-yellow-800">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm font-medium">
              Agent not responding — polling stopped after 10 minutes. The agent may have crashed.
            </span>
          </div>
        )}

        {/* Completed */}
        {run.status === 'completed' && (
          <div className="flex items-center gap-2 rounded-md bg-green-50 p-3 text-green-800">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">
              {isDryrun ? '드라이런 완료' : 'Replay completed successfully'}
            </span>
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

        {/* ── Verification result card ── */}
        {run.verification && (
          <div
            className={`flex items-start gap-3 rounded-md p-4 ${
              run.verification.success
                ? 'bg-green-50 text-green-800'
                : 'bg-orange-50 text-orange-800'
            }`}
          >
            {run.verification.success ? (
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
            ) : (
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            )}
            <div>
              <p className="text-sm font-semibold">
                {run.verification.success ? 'AI 검증 통과' : 'AI 검증 실패'}
              </p>
              <p className="mt-1 text-sm">{run.verification.evidence}</p>
            </div>
          </div>
        )}

        {/* ── Diagnosis report card ── */}
        {run.diagnosis && (
          <div className="rounded-md border border-orange-200 bg-orange-50 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-orange-600" />
              <p className="text-sm font-semibold text-orange-800">AI 실패 진단</p>
              <Badge variant="outline" className="ml-auto text-xs">
                신뢰도 {Math.round(run.diagnosis.confidence * 100)}%
              </Badge>
            </div>
            <p className="text-sm text-orange-800">{run.diagnosis.cause}</p>
            {run.diagnosis.failed_step_fix && (
              <div className="rounded bg-white/60 p-3 text-sm space-y-1">
                <p className="font-medium text-orange-900">수정 제안</p>
                <div className="grid grid-cols-[100px_1fr] gap-1 text-orange-800">
                  <span className="text-muted-foreground">대상</span>
                  <span>{run.diagnosis.failed_step_fix.target_description}</span>
                  <span className="text-muted-foreground">힌트</span>
                  <span>{run.diagnosis.failed_step_fix.hint}</span>
                  <span className="text-muted-foreground">제안 타입</span>
                  <span>{run.diagnosis.failed_step_fix.suggested_type}</span>
                  <span className="text-muted-foreground">제안 값</span>
                  <span>{run.diagnosis.failed_step_fix.suggested_value}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Dry-run results table ── */}
        {isDryrun && run.dryrun_results && run.dryrun_results.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-semibold">드라이런 결과</p>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">#</th>
                    <th className="px-3 py-2 text-left font-medium">타입</th>
                    <th className="px-3 py-2 text-left font-medium">설명</th>
                    <th className="px-3 py-2 text-left font-medium">상태</th>
                    <th className="px-3 py-2 text-left font-medium">좌표</th>
                    <th className="px-3 py-2 text-left font-medium">신뢰도</th>
                    <th className="px-3 py-2 text-left font-medium">탐지 방법</th>
                  </tr>
                </thead>
                <tbody>
                  {run.dryrun_results.map((dr: DryrunStepResult) => (
                    <tr key={dr.step_index} className="border-t">
                      <td className="px-3 py-2 text-muted-foreground">{dr.step_index}</td>
                      <td className="px-3 py-2">
                        <Badge variant="outline" className="text-xs">{dr.step_type}</Badge>
                      </td>
                      <td className="px-3 py-2 max-w-[200px] truncate">{dr.description}</td>
                      <td className="px-3 py-2">
                        {dr.skipped ? (
                          <span className="text-muted-foreground text-xs">
                            {dr.skip_reason ?? 'skipped'}
                          </span>
                        ) : (
                          <span className="text-green-600 font-medium text-xs">탐지 성공</span>
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {dr.expected_x != null && dr.expected_y != null
                          ? `(${dr.expected_x}, ${dr.expected_y})`
                          : '—'}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {dr.confidence != null
                          ? `${Math.round(dr.confidence * 100)}%`
                          : '—'}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {dr.method ? (METHOD_LABELS[dr.method] ?? dr.method) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
