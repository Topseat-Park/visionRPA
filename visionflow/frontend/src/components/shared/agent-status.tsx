import { useAgentStatus } from '@/hooks/use-agent-status';
import { AGENT_STATE_LABELS } from '@/lib/constants';

const STATE_COLORS: Record<string, string> = {
  offline: 'bg-gray-400',
  online: 'bg-green-500',
  recording: 'bg-red-500 animate-pulse',
  replaying: 'bg-orange-500 animate-pulse',
  paused_conflict: 'bg-yellow-500',
  waiting_hitl: 'bg-blue-500 animate-pulse',
};

export function AgentStatusIndicator() {
  const { data, isError } = useAgentStatus();

  const state = isError || !data ? 'offline' : data.agent_state;
  const label = AGENT_STATE_LABELS[state] ?? state;
  const color = STATE_COLORS[state] ?? 'bg-gray-400';

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-muted-foreground">{label}</span>
      {data?.recording_event_count != null && data.recording_event_count > 0 && (
        <span className="text-xs text-muted-foreground">
          ({data.recording_event_count}개 이벤트)
        </span>
      )}
    </div>
  );
}
