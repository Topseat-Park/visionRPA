import { Pause, Play, Square } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useAgentStatus } from '@/hooks/use-agent-status';
import { api } from '@/lib/api-client';

interface AgentStatusResponse {
  agent_state: string;
}

export function RecordingControls({ onStop }: { onStop: () => void }) {
  const { data: status } = useAgentStatus();
  const pauseMut = useMutation({
    mutationFn: () =>
      api.post('/agent/command', { type: 'pause_recording', payload: {} }),
  });

  const resumeMut = useMutation({
    mutationFn: () =>
      api.post('/agent/command', { type: 'resume_recording', payload: {} }),
  });

  const stopMut = useMutation({
    mutationFn: async () => {
      await api.post('/agent/command', { type: 'stop_recording', payload: {} });
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 500));
        const s = await api.get<AgentStatusResponse>('/agent/status');
        if (s.agent_state !== 'recording') return;
      }
    },
    onSuccess: () => onStop(),
  });

  const isRecording = status?.agent_state === 'recording';
  const eventCount = status?.recording_event_count ?? 0;
  const elapsed = status?.recording_elapsed ?? 0;

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <Card className="flex flex-col items-center gap-4 p-8">
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-3 animate-pulse rounded-full bg-red-500" />
          <span className="text-lg font-semibold">
            {stopMut.isPending ? '중지 중...' : '녹화 중'}
          </span>
        </div>

        <div className="flex gap-8 text-center">
          <div>
            <div className="text-3xl font-bold tabular-nums">
              {formatTime(elapsed)}
            </div>
            <div className="text-xs text-muted-foreground">경과 시간</div>
          </div>
          <div>
            <div className="text-3xl font-bold tabular-nums">{eventCount}</div>
            <div className="text-xs text-muted-foreground">이벤트</div>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          F9: 일시정지/재개 | F10: 중지
        </p>

        <div className="flex gap-3">
          <Button
            variant="outline"
            size="lg"
            onClick={() =>
              isRecording ? pauseMut.mutate() : resumeMut.mutate()
            }
            disabled={stopMut.isPending}
          >
            {isRecording ? (
              <>
                <Pause className="mr-2 h-4 w-4" /> 일시정지
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" /> 재개
              </>
            )}
          </Button>

          <Button
            variant="destructive"
            size="lg"
            onClick={() => stopMut.mutate()}
            disabled={stopMut.isPending}
          >
            <Square className="mr-2 h-4 w-4" />
            {stopMut.isPending ? '중지 중...' : '녹화 중지'}
          </Button>
        </div>
      </Card>
    </div>
  );
}
