export type StepType =
  | 'cmd'
  | 'hotkey'
  | 'clipboard_paste'
  | 'vision_click'
  | 'navigate'
  | 'scroll'
  | 'drag'
  | 'wait'
  | 'file_open'
  | 'file_write'
  | 'focus_window';

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
  crop_ref?: string | null;
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

export interface WorkflowSummary {
  flow_summary: string;
  attention_steps: string[];
  improvement_suggestions: string[];
  recommended_first_run: 'dryrun' | 'manual' | 'auto';
  estimated_duration_sec?: number | null;
}

export interface GenerateWorkflowResponse {
  workflow: Workflow;
  summary: WorkflowSummary | null;
  generation_method: 'ai' | 'rule_based';
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
