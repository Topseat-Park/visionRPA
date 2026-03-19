export const STEP_TYPE_LABELS: Record<string, string> = {
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

export const EVENT_TYPE_LABELS: Record<string, string> = {
  app_launch: '앱 실행',
  click: '클릭',
  double_click: '더블클릭',
  type: '입력',
  key: '키',
  scroll: '스크롤',
  drag: '드래그',
  window_change: '창 전환',
};

export const AGENT_STATE_LABELS: Record<string, string> = {
  offline: '오프라인',
  online: '온라인',
  recording: '녹화 중',
  replaying: '실행 중',
  paused_conflict: '일시정지 (충돌)',
  waiting_hitl: '승인 대기',
};
