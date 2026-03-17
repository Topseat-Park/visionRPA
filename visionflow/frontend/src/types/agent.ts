export type AgentState =
  | 'offline'
  | 'online'
  | 'recording'
  | 'replaying'
  | 'paused_conflict'
  | 'waiting_hitl';

export interface AgentStatus {
  agent_state: AgentState;
  last_command_id: string | null;
  recording_session_id: string | null;
  recording_event_count: number;
  recording_elapsed: number;
  replay_run_id: string | null;
  replay_workflow_id: string | null;
  replay_current_step: number;
  replay_total_steps: number;
  replay_step_description: string | null;
  error: string | null;
}

export type CommandType =
  | 'start_recording'
  | 'pause_recording'
  | 'resume_recording'
  | 'stop_recording'
  | 'start_run'
  | 'abort_run'
  | 'hitl_response'
  | 'ping';
