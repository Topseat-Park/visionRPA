import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronUp,
  ArrowUp,
  ArrowDown,
  Trash2,
  Play,
  Save,
  Plus,
  Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api-client';
import type { Workflow, WorkflowStep, WorkflowSummary, StepType, OnFailure, SpeedMode } from '@/types/workflow';

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const STEP_TYPE_LABELS: Record<string, string> = {
  cmd: '명령어',
  hotkey: '단축키',
  clipboard_paste: '텍스트 입력',
  vision_click: '화면 클릭',
  navigate: '페이지 이동',
  scroll: '스크롤',
  drag: '드래그',
  wait: '대기',
  file_open: '파일 열기',
  file_write: '파일 쓰기',
  focus_window: '창 활성화',
};

const STEP_TYPE_COLORS: Record<string, string> = {
  cmd: 'bg-red-100 text-red-700',
  hotkey: 'bg-purple-100 text-purple-700',
  clipboard_paste: 'bg-green-100 text-green-700',
  vision_click: 'bg-blue-100 text-blue-700',
  navigate: 'bg-cyan-100 text-cyan-700',
  scroll: 'bg-yellow-100 text-yellow-700',
  drag: 'bg-orange-100 text-orange-700',
  wait: 'bg-gray-100 text-gray-700',
  file_open: 'bg-emerald-100 text-emerald-700',
  file_write: 'bg-teal-100 text-teal-700',
  focus_window: 'bg-indigo-100 text-indigo-700',
};

const STEP_TYPES: StepType[] = [
  'cmd',
  'hotkey',
  'clipboard_paste',
  'vision_click',
  'navigate',
  'scroll',
  'drag',
  'wait',
  'file_open',
  'file_write',
  'focus_window',
];

const ON_FAILURE_OPTIONS: OnFailure[] = ['retry', 'human', 'skip', 'abort'];
const SPEED_OPTIONS: SpeedMode[] = ['fast', 'normal', 'slow'];

interface VersionEntry {
  version: number;
  step_count: number;
  created_at?: string;
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

export function WorkflowEditPage() {
  const { workflowId } = useParams({ strict: false });
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  /* ---- Local editing state ---- */
  const [editedSteps, setEditedSteps] = useState<WorkflowStep[]>([]);
  const [editedName, setEditedName] = useState('');
  const [editedDescription, setEditedDescription] = useState('');
  const [expandedStepId, setExpandedStepId] = useState<number | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [versionsOpen, setVersionsOpen] = useState(false);

  /* ---- Queries ---- */
  const {
    data: workflow,
    isLoading,
    error,
  } = useQuery<Workflow>({
    queryKey: ['workflow', workflowId],
    queryFn: () => api.get<Workflow>(`/workflows/${workflowId}`),
    enabled: !!workflowId,
  });

  const { data: versions } = useQuery<VersionEntry[]>({
    queryKey: ['workflow-versions', workflowId],
    queryFn: () => api.get<VersionEntry[]>(`/workflows/${workflowId}/versions`),
    enabled: !!workflowId,
  });

  const { data: summary } = useQuery<WorkflowSummary>({
    queryKey: ['workflow-summary', workflowId],
    queryFn: () => api.get<WorkflowSummary>(`/workflows/${workflowId}/summary`),
    enabled: !!workflowId,
    retry: false,
  });

  /* ---- Initialise editing state from fetched data ---- */
  useEffect(() => {
    if (workflow) {
      setEditedName(workflow.name);
      setEditedDescription(workflow.description);
      setEditedSteps(workflow.steps.map((s) => ({ ...s })));
      setIsDirty(false);
    }
  }, [workflow]);

  /* ---- Mutations ---- */
  const saveMut = useMutation({
    mutationFn: () => {
      // Re-index step IDs from 1 to avoid gaps after deletions
      const normalizedSteps = editedSteps.map((s, idx) => ({ ...s, id: idx + 1 }));
      return api.put<Workflow>(`/workflows/${workflowId}`, {
        name: editedName,
        description: editedDescription,
        steps: normalizedSteps,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] });
      queryClient.invalidateQueries({ queryKey: ['workflow-versions', workflowId] });
      setIsDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    },
  });

  const runMut = useMutation({
    mutationFn: (mode: string = 'normal') =>
      api.post<{ run_id: string }>(`/runs?workflow_id=${workflowId}&mode=${mode}`, {}),
    onSuccess: (data) => {
      navigate({ to: '/runs/$runId', params: { runId: data.run_id } });
    },
    onError: (e: Error) => setRunError(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: () => api.delete(`/workflows/${workflowId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      navigate({ to: '/' });
    },
  });

  /* ---- Helpers ---- */
  const markDirty = useCallback(() => setIsDirty(true), []);

  const updateStep = useCallback(
    (id: number, patch: Partial<WorkflowStep>) => {
      setEditedSteps((prev) =>
        prev.map((s) => (s.id === id ? { ...s, ...patch } : s)),
      );
      markDirty();
    },
    [markDirty],
  );

  const moveStep = useCallback(
    (index: number, direction: -1 | 1) => {
      setEditedSteps((prev) => {
        const next = [...prev];
        const target = index + direction;
        if (target < 0 || target >= next.length) return prev;
        [next[index], next[target]] = [next[target], next[index]];
        return next;
      });
      markDirty();
    },
    [markDirty],
  );

  const deleteStep = useCallback(
    (id: number) => {
      if (!window.confirm('이 스텝을 삭제하시겠습니까?')) return;
      setEditedSteps((prev) => prev.filter((s) => s.id !== id));
      if (expandedStepId === id) setExpandedStepId(null);
      markDirty();
    },
    [expandedStepId, markDirty],
  );

  const addStep = useCallback(() => {
    const newId =
      editedSteps.length > 0
        ? Math.max(...editedSteps.map((s) => s.id)) + 1
        : 1;
    const newStep: WorkflowStep = {
      id: newId,
      type: 'cmd',
      description: '',
      value: '',
      timeout_sec: 30,
      speed: 'normal',
      on_failure: 'human',
    };
    setEditedSteps((prev) => [...prev, newStep]);
    setExpandedStepId(newId);
    markDirty();
  }, [editedSteps, markDirty]);

  const toggleStep = useCallback(
    (id: number) => {
      setExpandedStepId((prev) => (prev === id ? null : id));
    },
    [],
  );

  /* ---- Loading / error states ---- */
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
        <h2 className="text-2xl font-bold">워크플로우를 찾을 수 없습니다</h2>
        <Link to="/">
          <Button variant="outline">돌아가기</Button>
        </Link>
      </div>
    );
  }

  /* ---- Render ---- */
  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-16">
      {/* ========== Header ========== */}
      <Card className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-3">
            <Input
              value={editedName}
              onChange={(e) => {
                setEditedName(e.target.value);
                markDirty();
              }}
              placeholder="워크플로우 이름"
              className="text-lg font-semibold"
            />
            <Textarea
              value={editedDescription}
              onChange={(e) => {
                setEditedDescription(e.target.value);
                markDirty();
              }}
              placeholder="워크플로우 설명"
              rows={2}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">v{workflow.version}</Badge>
            <span className="text-sm text-muted-foreground">
              {editedSteps.length} step{editedSteps.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {isDirty && (
              <Button
                onClick={() => saveMut.mutate()}
                disabled={saveMut.isPending}
                variant="default"
              >
                <Save className="mr-2 h-4 w-4" />
                {saveMut.isPending ? '저장 중...' : '저장'}
              </Button>
            )}
            {saveSuccess && (
              <span className="text-sm font-medium text-green-600">저장됨!</span>
            )}
            <Button
              onClick={() => runMut.mutate('normal')}
              disabled={runMut.isPending || editedSteps.length === 0}
              variant="outline"
            >
              <Play className="mr-2 h-4 w-4" />
              {runMut.isPending ? '시작 중...' : '실행'}
            </Button>
            <Button
              onClick={() => runMut.mutate('dryrun')}
              disabled={runMut.isPending || editedSteps.length === 0}
              variant="outline"
            >
              <Eye className="mr-2 h-4 w-4" />
              드라이런
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
              title="워크플로우 삭제"
              onClick={() => {
                if (window.confirm('이 워크플로우를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
                  deleteMut.mutate();
                }
              }}
              disabled={deleteMut.isPending}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {saveMut.isError && (
          <p className="text-sm text-destructive">
            저장 실패:{(saveMut.error as Error).message}
          </p>
        )}
        {runError && <p className="text-sm text-destructive">{runError}</p>}
      </Card>

      {/* ========== AI Summary ========== */}
      {summary && (
        <Card className="space-y-3 p-5">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">AI 생성 요약</h3>
            <Badge variant="outline" className="text-xs">
              {summary.recommended_first_run === 'dryrun'
                ? '드라이런 권장'
                : summary.recommended_first_run === 'manual'
                  ? '수동 실행 권장'
                  : '자동 실행 가능'}
            </Badge>
            {summary.estimated_duration_sec != null && (
              <span className="text-xs text-muted-foreground">
                예상 {summary.estimated_duration_sec}초
              </span>
            )}
          </div>

          <p className="text-sm">{summary.flow_summary}</p>

          {summary.attention_steps.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-amber-600">주의 필요 스텝</p>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
                {summary.attention_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {summary.improvement_suggestions.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-blue-600">개선 제안</p>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
                {summary.improvement_suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {/* ========== 버전 이력 ========== */}
      {versions && versions.length > 0 && (
        <Card className="overflow-hidden">
          <button
            type="button"
            className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-medium hover:bg-muted/50"
            onClick={() => setVersionsOpen((v) => !v)}
          >
            <span>버전 이력 ({versions.length})</span>
            {versionsOpen ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
          {versionsOpen && (
            <div className="border-t px-5 py-3">
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li
                    key={v.version}
                    className="flex items-center justify-between rounded px-2 py-1.5 text-sm hover:bg-muted/40"
                  >
                    <span className="font-medium">v{v.version}</span>
                    <span className="text-muted-foreground">
                      {v.step_count} step{v.step_count !== 1 ? 's' : ''}
                      {v.created_at && (
                        <> &middot; {new Date(v.created_at).toLocaleDateString()}</>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {/* ========== Steps ========== */}
      {editedSteps.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          스텝이 없습니다. 스텝을 추가해주세요.
        </Card>
      ) : (
        <div className="space-y-2">
          {editedSteps.map((step, idx) => {
            const isExpanded = expandedStepId === step.id;
            return (
              <Card key={step.id} className="overflow-hidden">
                {/* ---- Collapsed row ---- */}
                <button
                  type="button"
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40"
                  onClick={() => toggleStep(step.id)}
                >
                  <span className="w-7 shrink-0 text-center text-sm font-semibold text-muted-foreground">
                    {idx + 1}
                  </span>
                  <span
                    className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                      STEP_TYPE_COLORS[step.type] ?? 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {STEP_TYPE_LABELS[step.type] ?? step.type}
                  </span>
                  <span className="flex-1 truncate text-sm">
                    {step.description || (
                      <span className="italic text-muted-foreground">설명 없음</span>
                    )}
                  </span>
                  <Badge variant="outline" className="shrink-0 text-xs">
                    {step.on_failure}
                  </Badge>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                </button>

                {/* ---- Expanded editor ---- */}
                {isExpanded && (
                  <div className="space-y-4 border-t bg-muted/20 px-5 py-4">
                    {/* Description */}
                    <FieldRow label="설명">
                      <Input
                        value={step.description}
                        onChange={(e) =>
                          updateStep(step.id, { description: e.target.value })
                        }
                        placeholder="스텝 설명"
                      />
                    </FieldRow>

                    {/* Value */}
                    <FieldRow label="값">
                      {step.type === 'clipboard_paste' ? (
                        <Textarea
                          value={step.value ?? ''}
                          onChange={(e) =>
                            updateStep(step.id, { value: e.target.value })
                          }
                          placeholder="붙여넣을 텍스트"
                          rows={3}
                        />
                      ) : (
                        <Input
                          value={step.value ?? ''}
                          onChange={(e) =>
                            updateStep(step.id, { value: e.target.value })
                          }
                          placeholder="값"
                        />
                      )}
                    </FieldRow>

                    {/* Type */}
                    <FieldRow label="유형">
                      <select
                        value={step.type}
                        onChange={(e) =>
                          updateStep(step.id, { type: e.target.value as StepType })
                        }
                        className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                      >
                        {STEP_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {STEP_TYPE_LABELS[t]}
                          </option>
                        ))}
                      </select>
                    </FieldRow>

                    {/* On Failure */}
                    <FieldRow label="실패 시">
                      <select
                        value={step.on_failure}
                        onChange={(e) =>
                          updateStep(step.id, {
                            on_failure: e.target.value as OnFailure,
                          })
                        }
                        className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                      >
                        {ON_FAILURE_OPTIONS.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </FieldRow>

                    {/* Timeout */}
                    <FieldRow label="타임아웃(초)">
                      <Input
                        type="number"
                        min={0}
                        value={step.timeout_sec}
                        onChange={(e) =>
                          updateStep(step.id, {
                            timeout_sec: Number(e.target.value),
                          })
                        }
                      />
                    </FieldRow>

                    {/* Speed */}
                    <FieldRow label="속도">
                      <select
                        value={step.speed}
                        onChange={(e) =>
                          updateStep(step.id, {
                            speed: e.target.value as SpeedMode,
                          })
                        }
                        className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                      >
                        {SPEED_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </FieldRow>

                    {/* Conditional fields: vision_click */}
                    {step.type === 'vision_click' && (
                      <>
                        <FieldRow label="클릭 대상">
                          <Input
                            value={step.target_description ?? ''}
                            onChange={(e) =>
                              updateStep(step.id, {
                                target_description: e.target.value,
                              })
                            }
                            placeholder="클릭 대상 설명"
                          />
                        </FieldRow>
                        <FieldRow label="힌트">
                          <Input
                            value={step.hint ?? ''}
                            onChange={(e) =>
                              updateStep(step.id, { hint: e.target.value })
                            }
                            placeholder="요소 탐지 힌트"
                          />
                        </FieldRow>
                      </>
                    )}

                    {/* Conditional field: wait */}
                    {step.type === 'wait' && (
                      <FieldRow label="대기 조건">
                        <Input
                          value={step.wait_condition ?? ''}
                          onChange={(e) =>
                            updateStep(step.id, {
                              wait_condition: e.target.value,
                            })
                          }
                          placeholder="대기 조건"
                        />
                      </FieldRow>
                    )}

                    {/* Conditional fields: file_open */}
                    {step.type === 'file_open' && (
                      <p className="text-xs text-muted-foreground">
                        값(Value)에 파일 경로를 입력하세요. 기본 앱으로 열립니다.
                      </p>
                    )}

                    {/* Conditional fields: file_write */}
                    {step.type === 'file_write' && (
                      <p className="text-xs text-muted-foreground">
                        값(Value) 형식: <code className="rounded bg-muted px-1">파일경로|||내용</code>
                        {' '}(예: <code className="rounded bg-muted px-1">C:\output.txt|||Hello World</code>)
                      </p>
                    )}

                    {/* Conditional fields: focus_window */}
                    {step.type === 'focus_window' && (
                      <p className="text-xs text-muted-foreground">
                        값(Value)에 창 제목 키워드를 입력하세요. 이미 열려있는 앱 창을 찾아 활성화합니다.
                        {' '}(예: <code className="rounded bg-muted px-1">Chrome</code>, <code className="rounded bg-muted px-1">Excel - 매출보고서.xlsx</code>)
                      </p>
                    )}

                    {/* ---- Step manipulation buttons ---- */}
                    <div className="flex items-center gap-2 border-t pt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={idx === 0}
                        onClick={() => moveStep(idx, -1)}
                        title="Move up"
                      >
                        <ArrowUp className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={idx === editedSteps.length - 1}
                        onClick={() => moveStep(idx, 1)}
                        title="Move down"
                      >
                        <ArrowDown className="h-4 w-4" />
                      </Button>
                      <div className="flex-1" />
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => deleteStep(step.id)}
                        title="Delete step"
                      >
                        <Trash2 className="mr-1.5 h-4 w-4" />
                        삭제
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* ========== Add Step ========== */}
      <Button variant="outline" className="w-full" onClick={addStep}>
        <Plus className="mr-2 h-4 w-4" />
        스텝 추가
      </Button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Small helper for consistent form layout                           */
/* ------------------------------------------------------------------ */

function FieldRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[120px_1fr] items-start gap-3">
      <label className="pt-1.5 text-sm font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
