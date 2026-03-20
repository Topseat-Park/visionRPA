import { useState, useEffect, useRef } from 'react';
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
  MousePointer,
  Check,
  X,
  Pencil,
  Clock,
  ChevronDown,
  Monitor,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api-client';
import type { RunMeta, DryrunStepResult, ComputerUseTurn } from '@/types/run';

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

const ACTION_LABELS: Record<string, string> = {
  click_at: '클릭',
  type_text_at: '텍스트 입력',
  scroll_document: '스크롤',
  scroll_at: '스크롤',
  key_combination: '단축키',
  navigate: '페이지 이동',
  go_back: '뒤로 가기',
  wait_5_seconds: '5초 대기',
  hover_at: '마우스 호버',
  drag_and_drop: '드래그 앤 드롭',
  safety_decision: '안전 확인',
};

function formatElapsed(startedAt: string): string {
  const elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export function RunMonitorPage() {
  const { runId } = useParams({ strict: false });
  const navigate = useNavigate();
  const turnsEndRef = useRef<HTMLDivElement>(null);

  const { data: run, isLoading } = useQuery<RunMeta>({
    queryKey: ['run', runId],
    queryFn: () => api.get<RunMeta>(`/runs/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const status = data.status;
      if (status !== 'running' && status !== 'pending') return false;
      const elapsed = Date.now() - new Date(data.started_at).getTime();
      if (elapsed > POLLING_TIMEOUT_MS) return false;
      return 1000;
    },
  });

  const abortMut = useMutation({
    mutationFn: () => api.post(`/runs/${runId}/abort`, {}),
  });

  // HITL state
  const [modifyMode, setModifyMode] = useState(false);
  const [modX, setModX] = useState('');
  const [modY, setModY] = useState('');
  // Computer Use: selected turn for screenshot preview
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  // Session timer
  const [elapsed, setElapsed] = useState('0:00');

  const hitlMut = useMutation({
    mutationFn: (body: { action: string; modified_x?: number; modified_y?: number }) =>
      api.post(`/runs/${runId}/hitl`, body),
    onSuccess: () => {
      setModifyMode(false);
    },
  });

  // Update timer every second while active
  useEffect(() => {
    if (!run || (run.status !== 'running' && run.status !== 'pending')) return;
    const iv = setInterval(() => setElapsed(formatElapsed(run.started_at)), 1000);
    return () => clearInterval(iv);
  }, [run?.status, run?.started_at]);

  // Auto-scroll turns list
  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [run?.computer_use_turns?.length]);

  // Auto-select latest turn
  useEffect(() => {
    if (run?.computer_use_turns?.length) {
      const lastTurn = run.computer_use_turns[run.computer_use_turns.length - 1];
      setSelectedTurn(lastTurn.turn);
    }
  }, [run?.computer_use_turns?.length]);

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
  const isComputerUse = run.mode === 'computer_use';

  // Computer Use mode: 2-panel layout
  if (isComputerUse) {
    const turns = run.computer_use_turns ?? [];
    const maxTurns = 30; // default max
    const screenshotUrl = selectedTurn
      ? `/api/v1/runs/${runId}/turns/turn_${String(selectedTurn).padStart(3, '0')}_${turns.find((t) => t.turn === selectedTurn)?.action ?? 'unknown'}.jpg`
      : null;

    return (
      <div className="flex h-[calc(100vh-80px)] flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-3">
            <Monitor className="h-5 w-5 text-primary" />
            <div>
              <h2 className="text-lg font-bold">Computer Use</h2>
              <p className="text-xs text-muted-foreground">{run.workflow_name}</p>
            </div>
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
                <Square className="mr-1 h-3 w-3" /> 중단
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                navigate({
                  to: '/workflows/$workflowId',
                  params: { workflowId: run.workflow_id },
                })
              }
            >
              <ArrowLeft className="mr-1 h-3 w-3" /> 워크플로우
            </Button>
          </div>
        </div>

        {/* 2-panel body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel: Goal + Turn cards */}
          <div className="flex w-[420px] shrink-0 flex-col border-r">
            {/* Goal description */}
            <div className="border-b bg-muted/30 p-4">
              <p className="text-sm leading-relaxed">
                {run.workflow_name}
              </p>
            </div>

            {/* Turns list */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {turns.length === 0 && isActive && (
                <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  <span className="text-sm text-muted-foreground">화면 분석 중...</span>
                </div>
              )}

              {turns.map((t: ComputerUseTurn, i: number) => (
                <Card
                  key={i}
                  className={`cursor-pointer p-4 transition-colors hover:bg-muted/40 ${
                    selectedTurn === t.turn ? 'ring-2 ring-primary' : ''
                  }`}
                  onClick={() => setSelectedTurn(t.turn)}
                >
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                      {t.turn}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <p className="text-sm font-medium">
                        {ACTION_LABELS[t.action] ?? t.action}
                      </p>
                      {t.reasoning && (
                        <p className="text-xs leading-relaxed text-muted-foreground line-clamp-3">
                          {t.reasoning}
                        </p>
                      )}
                      <div className="flex items-center gap-2">
                        <ChevronDown className="h-3 w-3 text-muted-foreground" />
                        <Badge variant="outline" className="text-[10px] font-mono">
                          {t.action}
                        </Badge>
                        {t.result === 'success' ? (
                          <CheckCircle className="h-3 w-3 text-green-500" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-500" />
                        )}
                      </div>
                    </div>
                  </div>
                </Card>
              ))}

              {/* Auto-scroll anchor */}
              <div ref={turnsEndRef} />

              {isActive && turns.length > 0 && (
                <div className="flex items-center gap-2 p-2">
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">다음 액션 대기 중...</span>
                </div>
              )}
            </div>
          </div>

          {/* Right panel: Screenshot preview */}
          <div className="flex flex-1 flex-col bg-muted/10">
            <div className="flex-1 flex items-center justify-center overflow-auto p-4">
              {screenshotUrl ? (
                <img
                  src={screenshotUrl}
                  alt={`Turn ${selectedTurn} screenshot`}
                  className="max-h-full max-w-full rounded-lg border shadow-sm object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
              ) : (
                <div className="text-center text-muted-foreground">
                  <Monitor className="mx-auto mb-2 h-12 w-12 opacity-30" />
                  <p className="text-sm">턴을 선택하면 스크린샷이 표시됩니다</p>
                </div>
              )}
            </div>

            {/* Verification / Diagnosis cards */}
            {(run.verification || run.diagnosis) && (
              <div className="space-y-2 border-t p-4">
                {run.verification && (
                  <div
                    className={`flex items-start gap-2 rounded-md p-3 text-sm ${
                      run.verification.success
                        ? 'bg-green-50 text-green-800'
                        : 'bg-orange-50 text-orange-800'
                    }`}
                  >
                    {run.verification.success ? (
                      <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                    ) : (
                      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    <div>
                      <p className="font-semibold">
                        {run.verification.success ? 'AI 검증 통과' : 'AI 검증 실패'}
                      </p>
                      <p className="mt-0.5 text-xs">{run.verification.evidence}</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Bottom bar: Session timer + Stop */}
        <div className="flex items-center justify-between border-t bg-background px-4 py-2.5">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>
                세션 시간: <span className="font-mono font-medium text-foreground">{elapsed}</span>
                {' / '}
                <span className="font-mono">5:00</span>
              </span>
            </div>
            {isActive && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => abortMut.mutate()}
                disabled={abortMut.isPending}
              >
                <Square className="mr-1.5 h-3 w-3" /> Stop
              </Button>
            )}
            {!isActive && run.status === 'completed' && (
              <Badge variant="outline" className="text-green-600">
                <CheckCircle className="mr-1 h-3 w-3" /> 완료
              </Badge>
            )}
            {!isActive && run.status === 'failed' && (
              <Badge variant="destructive">
                <XCircle className="mr-1 h-3 w-3" /> 실패
              </Badge>
            )}
          </div>
          <span className="text-xs text-muted-foreground">
            Gemini 2.5 Computer Use
          </span>
        </div>
      </div>
    );
  }

  // ── Normal / Dryrun / Test Step mode (existing layout) ──────────
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

        {/* ── HITL Panel ── */}
        {run.hitl_request && (
          <div className="rounded-md border-2 border-blue-300 bg-blue-50 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <MousePointer className="h-5 w-5 text-blue-600" />
              <p className="text-sm font-semibold text-blue-800">
                Human-in-the-Loop 승인 대기
              </p>
              <Badge variant="outline" className="ml-auto text-xs">
                스텝 {run.hitl_request.step_index}
              </Badge>
            </div>

            <p className="text-sm text-blue-800">{run.hitl_request.step_description}</p>

            <div className="grid grid-cols-2 gap-2 text-sm text-blue-800">
              <span className="text-muted-foreground">클릭 대상</span>
              <span>{run.hitl_request.target_description || '—'}</span>
              <span className="text-muted-foreground">예상 좌표</span>
              <span className="font-mono">
                ({run.hitl_request.predicted_x}, {run.hitl_request.predicted_y})
              </span>
              {run.hitl_request.confidence != null && (
                <>
                  <span className="text-muted-foreground">신뢰도</span>
                  <span>{Math.round(run.hitl_request.confidence * 100)}%</span>
                </>
              )}
              {run.hitl_request.method && (
                <>
                  <span className="text-muted-foreground">탐지 방법</span>
                  <span>{METHOD_LABELS[run.hitl_request.method] ?? run.hitl_request.method}</span>
                </>
              )}
            </div>

            {modifyMode ? (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Input
                    type="number"
                    placeholder="X"
                    value={modX}
                    onChange={(e) => setModX(e.target.value)}
                    className="w-24"
                  />
                  <Input
                    type="number"
                    placeholder="Y"
                    value={modY}
                    onChange={(e) => setModY(e.target.value)}
                    className="w-24"
                  />
                  <Button
                    size="sm"
                    onClick={() =>
                      hitlMut.mutate({
                        action: 'modify',
                        modified_x: Number(modX),
                        modified_y: Number(modY),
                      })
                    }
                    disabled={hitlMut.isPending || !modX || !modY}
                  >
                    <Check className="mr-1 h-3 w-3" /> 적용
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setModifyMode(false)}>
                    취소
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  className="bg-green-600 hover:bg-green-700"
                  onClick={() => hitlMut.mutate({ action: 'approve' })}
                  disabled={hitlMut.isPending}
                >
                  <Check className="mr-1 h-3 w-3" /> 승인
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setModX(String(run.hitl_request!.predicted_x));
                    setModY(String(run.hitl_request!.predicted_y));
                    setModifyMode(true);
                  }}
                  disabled={hitlMut.isPending}
                >
                  <Pencil className="mr-1 h-3 w-3" /> 수정
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => hitlMut.mutate({ action: 'cancel' })}
                  disabled={hitlMut.isPending}
                >
                  <X className="mr-1 h-3 w-3" /> 취소
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Current step */}
        {isActive && !run.hitl_request && (
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
