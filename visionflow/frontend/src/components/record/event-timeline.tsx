import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Wand2, X, MousePointerClick, Keyboard, Type, Move, AppWindow, ArrowUpDown, GripHorizontal, Timer } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api-client';
import type { RecordEvent } from '@/types/session';

interface EventTimelineProps {
  sessionId: string;
  onGenerate: () => void;
}

const EVENT_META: Record<string, { label: string; color: string; icon: typeof MousePointerClick }> = {
  click:         { label: '클릭',     color: 'bg-blue-500',   icon: MousePointerClick },
  double_click:  { label: '더블클릭', color: 'bg-blue-600',   icon: MousePointerClick },
  type:          { label: '입력',     color: 'bg-green-500',  icon: Type },
  key:           { label: '키',       color: 'bg-purple-500', icon: Keyboard },
  scroll:        { label: '스크롤',   color: 'bg-yellow-500', icon: ArrowUpDown },
  drag:          { label: '드래그',   color: 'bg-orange-500', icon: GripHorizontal },
  app_launch:    { label: '앱 실행',  color: 'bg-red-500',    icon: AppWindow },
  window_change: { label: '창 전환',  color: 'bg-cyan-500',   icon: Move },
};

export function EventTimeline({ sessionId, onGenerate }: EventTimelineProps) {
  const [expandedScreenshot, setExpandedScreenshot] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['session-events', sessionId],
    queryFn: () =>
      api.get<{ events: RecordEvent[]; total: number }>(
        `/sessions/${sessionId}/events`
      ),
  });

  const events = data?.events ?? [];

  // Summary stats
  const stats = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ev of events) {
      counts[ev.event_type] = (counts[ev.event_type] ?? 0) + 1;
    }
    return counts;
  }, [events]);

  const canGenerate = events.length >= 3;

  return (
    <div className="space-y-5">
      {/* ── Summary bar ── */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold">녹화 완료</h3>
            <p className="text-sm text-muted-foreground">
              총 <strong>{events.length}</strong>개 이벤트가 캡처되었습니다
            </p>
          </div>
          <Button onClick={onGenerate} disabled={!canGenerate} size="lg">
            <Wand2 className="mr-2 h-4 w-4" />
            AI 워크플로우 생성
          </Button>
        </div>

        {/* Event type breakdown */}
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(stats).map(([type, count]) => {
            const meta = EVENT_META[type];
            if (!meta) return null;
            const Icon = meta.icon;
            return (
              <Badge key={type} variant="secondary" className="gap-1.5 px-2.5 py-1">
                <Icon className="h-3 w-3" />
                {meta.label} {count}
              </Badge>
            );
          })}
        </div>

        {!canGenerate && events.length > 0 && (
          <p className="mt-2 text-sm text-destructive">
            워크플로우를 생성하려면 최소 3개 이벤트가 필요합니다.
          </p>
        )}
      </Card>

      {isLoading && <p className="text-muted-foreground">이벤트 불러오는 중...</p>}

      {/* ── Storyboard ── */}
      <ScrollArea className="h-[62vh]">
        <div className="grid gap-3 pr-4 md:grid-cols-2">
          {events.map((ev) => (
            <StoryboardCard
              key={ev.seq}
              event={ev}
              sessionId={sessionId}
              onScreenshotClick={setExpandedScreenshot}
            />
          ))}
        </div>
      </ScrollArea>

      {/* ── Bottom generate bar (sticky) ── */}
      {canGenerate && (
        <div className="sticky bottom-0 flex items-center justify-between rounded-lg border bg-card/95 p-3 shadow-lg backdrop-blur">
          <p className="text-sm text-muted-foreground">
            이벤트를 확인했다면 AI로 최적화된 워크플로우를 생성하세요
          </p>
          <Button onClick={onGenerate} size="lg">
            <Wand2 className="mr-2 h-4 w-4" />
            워크플로우 생성
          </Button>
        </div>
      )}

      {/* ── Fullscreen screenshot ── */}
      {expandedScreenshot && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
          onClick={() => setExpandedScreenshot(null)}
        >
          <button
            className="absolute right-4 top-4 rounded-full bg-white/20 p-2 text-white hover:bg-white/30"
            onClick={() => setExpandedScreenshot(null)}
          >
            <X className="h-6 w-6" />
          </button>
          <img
            src={expandedScreenshot}
            alt="스크린샷"
            className="max-h-[92vh] max-w-[92vw] rounded-lg shadow-2xl"
          />
        </div>
      )}
    </div>
  );
}

/* ── Storyboard Card ─────────────────────────────────────── */

function StoryboardCard({
  event,
  sessionId,
  onScreenshotClick,
}: {
  event: RecordEvent;
  sessionId: string;
  onScreenshotClick: (url: string) => void;
}) {
  const meta = EVENT_META[event.event_type] ?? { label: event.event_type, color: 'bg-gray-500', icon: Timer };
  const Icon = meta.icon;

  const screenshotFilename = event.screenshot_path
    ? event.screenshot_path.split(/[/\\]/).pop()
    : null;
  const screenshotUrl = screenshotFilename
    ? `/api/v1/sessions/${sessionId}/screenshots/${screenshotFilename}`
    : null;

  return (
    <Card className="group overflow-hidden">
      {/* Screenshot — hero element */}
      {screenshotUrl ? (
        <div
          className="relative cursor-pointer"
          onClick={() => onScreenshotClick(screenshotUrl)}
        >
          <img
            src={screenshotUrl}
            alt={`이벤트 ${event.seq}`}
            className="aspect-video w-full object-cover transition group-hover:brightness-95"
            loading="lazy"
          />
          {/* Overlay badge */}
          <div className="absolute left-2 top-2 flex items-center gap-1.5">
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white ${meta.color}`}>
              {event.seq}
            </span>
            <Badge className={`${meta.color} border-0 text-white text-xs`}>
              <Icon className="mr-1 h-3 w-3" />
              {meta.label}
            </Badge>
          </div>
        </div>
      ) : (
        <div className="flex aspect-video items-center justify-center bg-muted">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white ${meta.color}`}>
              {event.seq}
            </span>
            <Badge className={`${meta.color} border-0 text-white text-xs`}>
              <Icon className="mr-1 h-3 w-3" />
              {meta.label}
            </Badge>
          </div>
        </div>
      )}

      {/* Event detail */}
      <div className="px-3 py-2">
        <p className="text-sm leading-snug">{formatEventDetail(event)}</p>
      </div>
    </Card>
  );
}

/* ── Format helpers ──────────────────────────────────────── */

function formatEventDetail(ev: RecordEvent): string {
  switch (ev.event_type) {
    case 'click':
      return `${ev.button === 'right' ? '우' : '좌'}클릭 (${ev.x}, ${ev.y})`;
    case 'double_click':
      return `더블클릭 (${ev.x}, ${ev.y})`;
    case 'type':
      return `입력: "${String(ev.text ?? '').slice(0, 60)}"`;
    case 'key':
      return `${(ev.keys as string[])?.join(' + ') ?? String(ev.key ?? '')}`;
    case 'scroll':
      return `스크롤 ${ev.direction === 'up' ? '위' : '아래'} ${ev.amount ?? 1}칸`;
    case 'drag':
      return `드래그 (${ev.start_x}, ${ev.start_y}) → (${ev.end_x}, ${ev.end_y})`;
    case 'app_launch':
      return `${ev.app_name} 실행`;
    case 'window_change':
      return `${ev.window_title}`;
    default:
      return ev.event_type;
  }
}
