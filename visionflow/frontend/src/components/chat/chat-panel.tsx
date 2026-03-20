import { useState, useRef, useEffect } from 'react';
import {
  MessageCircle,
  Send,
  X,
  Trash2,
  Bot,
  User,
  Loader2,
  Play,
  FileText,
  Mic,
  Zap,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useChat, type ChatMessage } from '@/hooks/use-chat';

const FUNCTION_LABELS: Record<string, { label: string; icon: typeof Play }> = {
  create_workflow: { label: '워크플로우 생성', icon: FileText },
  edit_step: { label: '스텝 수정', icon: FileText },
  run_workflow: { label: '워크플로우 실행', icon: Play },
  run_computer_use: { label: 'Computer Use 실행', icon: Zap },
  start_recording: { label: '녹화 시작', icon: Mic },
  stop_recording: { label: '녹화 중지', icon: Mic },
  list_workflows: { label: '워크플로우 목록', icon: FileText },
  get_workflow: { label: '워크플로우 조회', icon: FileText },
  get_run_result: { label: '실행 결과', icon: Play },
  analyze_failure: { label: '실패 분석', icon: Zap },
};

const QUICK_ACTIONS = [
  { label: '워크플로우 목록', message: '워크플로우 목록 보여줘' },
  { label: '새 녹화', message: '새로 녹화 시작할게' },
  { label: '뭐 자동화할 수 있어?', message: '내 작업 중 자동화할 수 있는 게 있을까?' },
];

export function ChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const { messages, isLoading, sendMessage, clearChat } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    sendMessage(text);
  };

  // Toggle button (always visible)
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
        title="AI 비서"
      >
        <MessageCircle className="h-6 w-6" />
      </button>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 top-0 z-40 flex w-[380px] flex-col border-l bg-background shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <span className="font-semibold">AI 비서</span>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={clearChat} title="대화 초기화">
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setIsOpen(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-4 pt-8">
            <div className="text-center">
              <Bot className="mx-auto mb-2 h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">무엇을 도와드릴까요?</p>
            </div>
            <div className="space-y-2">
              {QUICK_ACTIONS.map((qa) => (
                <button
                  key={qa.label}
                  onClick={() => sendMessage(qa.message)}
                  className="w-full rounded-lg border p-3 text-left text-sm transition-colors hover:bg-muted/50"
                >
                  {qa.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>생각 중...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="메시지를 입력하세요..."
            className="flex-1 rounded-lg border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/50"
            disabled={isLoading}
          />
          <Button size="icon" onClick={handleSend} disabled={isLoading || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Bot className="h-4 w-4 text-primary" />
        </div>
      )}
      <div className={`max-w-[85%] space-y-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted'
          }`}
        >
          {message.content || (message.functionCalls?.length ? '' : '...')}
        </div>

        {/* Function call cards */}
        {message.functionCalls?.map((fc, i) => {
          const info = FUNCTION_LABELS[fc.name];
          const Icon = info?.icon ?? Zap;
          const isError = 'error' in (fc.result || {});
          return (
            <div key={i} className="rounded-lg border bg-muted/30 p-2.5 text-xs space-y-1">
              <div className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5 text-primary" />
                <span className="font-medium">{info?.label ?? fc.name}</span>
                {isError ? (
                  <XCircle className="ml-auto h-3.5 w-3.5 text-red-500" />
                ) : (
                  <CheckCircle className="ml-auto h-3.5 w-3.5 text-green-500" />
                )}
              </div>
              {fc.result && (
                <pre className="max-h-20 overflow-auto whitespace-pre-wrap text-[10px] text-muted-foreground">
                  {JSON.stringify(fc.result, null, 1)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
      {isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted">
          <User className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}
