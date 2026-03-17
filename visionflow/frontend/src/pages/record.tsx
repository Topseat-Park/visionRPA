import { useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { PreRecordForm } from '@/components/record/pre-record-form';
import { RecordingControls } from '@/components/record/recording-controls';
import { EventTimeline } from '@/components/record/event-timeline';
import { useRecordingStore } from '@/stores/recording-store';
import { useAgentStatus } from '@/hooks/use-agent-status';
import { api } from '@/lib/api-client';
import type { SessionMeta } from '@/types/session';

export function RecordPage() {
  const { step, setStep, sessionId, setSessionId, preRecordData, recordingStartedAt, markRecordingStarted, reset } =
    useRecordingStore();
  const { data: agentStatus } = useAgentStatus();

  // Reset to pre-record if agent is not recording and we're stuck in an old state.
  // Grace period: skip for the first 5 seconds after recording started to avoid
  // racing with the agent's command processing.
  useEffect(() => {
    if (
      step === 'recording' &&
      agentStatus &&
      agentStatus.agent_state !== 'recording'
    ) {
      // If recording was just started, allow time for agent to process
      if (recordingStartedAt && Date.now() - recordingStartedAt < 5000) {
        return;
      }
      // Agent is not recording but UI thinks it is — likely stale state
      if (sessionId) {
        setStep('timeline');
      } else {
        reset();
      }
    }
  }, [step, agentStatus, sessionId, recordingStartedAt, setStep, reset]);

  const startMut = useMutation({
    mutationFn: async () => {
      const session = await api.post<SessionMeta>('/sessions', {
        purpose: preRecordData.purpose,
        apps: preRecordData.apps,
        exceptions: preRecordData.exceptions,
        exception_notes: preRecordData.exception_notes || null,
        has_sensitive_info: preRecordData.has_sensitive_info,
      });
      await api.post('/agent/command', {
        type: 'start_recording',
        payload: {
          session_id: session.session_id,
          purpose: preRecordData.purpose,
          apps: preRecordData.apps,
          exceptions: preRecordData.exceptions,
          exception_notes: preRecordData.exception_notes || null,
          has_sensitive_info: preRecordData.has_sensitive_info,
        },
      });
      return session;
    },
    onSuccess: (session) => {
      setSessionId(session.session_id);
      markRecordingStarted();
      setStep('recording');
    },
  });

  const stepLabels: Record<string, string> = {
    'pre-record': 'Set up context, then start recording',
    recording: 'Perform your task — all actions are being captured',
    timeline: 'Review captured events and generate workflow',
    generating: 'AI is analyzing your recording...',
    done: 'Workflow generated successfully!',
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Record Workflow</h2>
        <p className="text-muted-foreground">{stepLabels[step]}</p>
      </div>

      {/* Step indicator */}
      <div className="flex gap-2">
        {(['pre-record', 'recording', 'timeline', 'generating'] as const).map(
          (s, i) => (
            <div
              key={s}
              className={`h-1.5 flex-1 rounded-full ${
                i <=
                ['pre-record', 'recording', 'timeline', 'generating'].indexOf(step)
                  ? 'bg-primary'
                  : 'bg-muted'
              }`}
            />
          )
        )}
      </div>

      {step === 'pre-record' && (
        <PreRecordForm onSubmit={() => startMut.mutate()} />
      )}

      {startMut.isError && (
        <p className="text-sm text-destructive">
          Failed to start: {startMut.error.message}
        </p>
      )}

      {step === 'recording' && (
        <RecordingControls onStop={() => setStep('timeline')} />
      )}

      {step === 'timeline' && sessionId && (
        <EventTimeline
          sessionId={sessionId}
          onGenerate={() => {
            setStep('generating');
            // Phase 2: will call POST /workflows/generate here
            setTimeout(() => setStep('done'), 2000);
          }}
        />
      )}

      {step === 'timeline' && !sessionId && (
        <div className="flex flex-col items-center gap-4 py-12">
          <p className="text-muted-foreground">No recording session found.</p>
          <button
            className="text-sm text-primary underline"
            onClick={() => reset()}
          >
            Start a new recording
          </button>
        </div>
      )}

      {step === 'generating' && (
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-muted-foreground">
            AI is analyzing your recording...
          </p>
        </div>
      )}

      {step === 'done' && (
        <div className="flex flex-col items-center gap-4 py-12">
          <p className="text-lg font-semibold">Workflow generated!</p>
          <p className="text-muted-foreground">
            Phase 2 will add the workflow editor here.
          </p>
          <button
            className="mt-2 text-sm text-primary underline"
            onClick={() => reset()}
          >
            Record another workflow
          </button>
        </div>
      )}
    </div>
  );
}
