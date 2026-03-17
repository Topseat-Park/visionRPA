export const STEP_TYPE_LABELS: Record<string, string> = {
  cmd: 'CMD',
  hotkey: 'Hotkey',
  clipboard_paste: 'Clipboard',
  vision_click: 'Vision Click',
  navigate: 'Navigate',
  scroll: 'Scroll',
  drag: 'Drag',
  wait: 'Wait',
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  app_launch: 'App Launch',
  click: 'Click',
  double_click: 'Double Click',
  type: 'Type',
  key: 'Key',
  scroll: 'Scroll',
  drag: 'Drag',
  window_change: 'Window Change',
};

export const AGENT_STATE_LABELS: Record<string, string> = {
  offline: 'Offline',
  online: 'Online',
  recording: 'Recording',
  replaying: 'Replaying',
  paused_conflict: 'Paused (Conflict)',
  waiting_hitl: 'Waiting for Approval',
};
