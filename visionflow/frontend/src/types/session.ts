export interface SessionMeta {
  session_id: string;
  created_at: string;
  purpose: string;
  apps: string[];
  event_count: number;
  status: string;
}

export interface RecordEvent {
  seq: number;
  timestamp: string;
  event_type: string;
  screenshot_path?: string;
  screenshot_meta?: {
    capture_width: number;
    capture_height: number;
    dpi_scale: number;
    monitor_index: number;
  };
  [key: string]: unknown;
}
