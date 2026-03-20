import { useState, useCallback, useRef } from 'react';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  functionCalls?: { name: string; args: Record<string, unknown>; result: Record<string, unknown> }[];
  timestamp: string;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() => {
    return localStorage.getItem('vf_chat_session_id');
  });
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    let assistantContent = '';
    const functionCalls: ChatMessage['functionCalls'] = [];

    try {
      abortRef.current = new AbortController();
      const res = await fetch('/api/v1/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text }),
        signal: abortRef.current.signal,
      });

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error('No reader');

      // Create initial assistant message
      const assistantId = crypto.randomUUID();
      setMessages(prev => [...prev, {
        id: assistantId,
        role: 'assistant',
        content: '',
        functionCalls: [],
        timestamp: new Date().toISOString(),
      }]);

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));

          if (data.type === 'session') {
            setSessionId(data.session_id);
            localStorage.setItem('vf_chat_session_id', data.session_id);
          } else if (data.type === 'text') {
            assistantContent += data.content;
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, content: assistantContent } : m
            ));
          } else if (data.type === 'function_call') {
            functionCalls.push({ name: data.name, args: data.args, result: data.result });
            setMessages(prev => prev.map(m =>
              m.id === assistantId ? { ...m, functionCalls: [...functionCalls] } : m
            ));
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        assistantContent = '오류가 발생했습니다. 다시 시도해주세요.';
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: assistantContent }];
          }
          return prev;
        });
      }
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const clearChat = useCallback(async () => {
    if (sessionId) {
      await fetch(`/api/v1/chat/history?session_id=${sessionId}`, { method: 'DELETE' });
    }
    setMessages([]);
    const newId = crypto.randomUUID();
    setSessionId(newId);
    localStorage.setItem('vf_chat_session_id', newId);
  }, [sessionId]);

  return { messages, isLoading, sendMessage, clearChat, sessionId };
}
