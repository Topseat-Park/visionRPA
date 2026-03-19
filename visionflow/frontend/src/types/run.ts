export interface Verification {
  success: boolean;
  evidence: string;
}

export interface FailedStepFix {
  target_description: string;
  hint: string;
  suggested_type: string;
  suggested_value: string;
}

export interface Diagnosis {
  cause: string;
  failed_step_fix: FailedStepFix;
  confidence: number;
}

export interface DryrunStepResult {
  step_index: number;
  step_type: string;
  description: string;
  skipped: boolean;
  skip_reason?: string;
  expected_x?: number | null;
  expected_y?: number | null;
  confidence?: number | null;
  method?: 'ai' | 'template' | 'fallback' | null;
}

export interface RunMeta {
  run_id: string;
  workflow_id: string;
  workflow_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'aborted';
  started_at: string;
  finished_at: string | null;
  current_step: number;
  total_steps: number;
  error: string | null;
  mode?: 'normal' | 'dryrun';
  verification?: Verification;
  diagnosis?: Diagnosis;
  dryrun_results?: DryrunStepResult[];
}
