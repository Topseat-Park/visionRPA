export type StepType =
  | 'cmd'
  | 'hotkey'
  | 'clipboard_paste'
  | 'vision_click'
  | 'navigate'
  | 'scroll'
  | 'drag'
  | 'wait';

export type OnFailure = 'retry' | 'human' | 'skip' | 'abort';
export type SpeedMode = 'fast' | 'normal' | 'slow';

export interface WorkflowStep {
  id: number;
  type: StepType;
  description: string;
  value?: string | null;
  target_description?: string | null;
  hint?: string | null;
  wait_condition?: string | null;
  timeout_sec: number;
  speed: SpeedMode;
  on_failure: OnFailure;
  screenshot_ref?: string | null;
}

export interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  version: number;
  last_successful_version?: number | null;
  default_speed: SpeedMode;
  steps: WorkflowStep[];
}

export interface WorkflowListItem {
  workflow_id: string;
  name: string;
  description: string;
  version: number;
  last_successful_version?: number | null;
  step_count: number;
  last_run_at?: string | null;
  success_rate?: number | null;
}
