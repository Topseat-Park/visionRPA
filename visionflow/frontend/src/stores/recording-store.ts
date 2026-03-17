import { create } from 'zustand';

type RecordingStep = 'pre-record' | 'recording' | 'timeline' | 'generating' | 'done';

interface PreRecordData {
  purpose: string;
  apps: string[];
  exceptions: string[];
  exception_notes: string;
  has_sensitive_info: boolean;
}

interface RecordingStore {
  step: RecordingStep;
  sessionId: string | null;
  preRecordData: PreRecordData;
  recordingStartedAt: number | null;
  setStep: (step: RecordingStep) => void;
  setSessionId: (id: string | null) => void;
  setPreRecordData: (data: Partial<PreRecordData>) => void;
  markRecordingStarted: () => void;
  reset: () => void;
}

const defaultPreRecord: PreRecordData = {
  purpose: '',
  apps: [],
  exceptions: [],
  exception_notes: '',
  has_sensitive_info: false,
};

export const useRecordingStore = create<RecordingStore>((set) => ({
  step: 'pre-record',
  sessionId: null,
  preRecordData: { ...defaultPreRecord },
  recordingStartedAt: null,
  setStep: (step) => set({ step }),
  setSessionId: (sessionId) => set({ sessionId }),
  setPreRecordData: (data) =>
    set((s) => ({ preRecordData: { ...s.preRecordData, ...data } })),
  markRecordingStarted: () => set({ recordingStartedAt: Date.now() }),
  reset: () =>
    set({ step: 'pre-record', sessionId: null, preRecordData: { ...defaultPreRecord }, recordingStartedAt: null }),
}));
