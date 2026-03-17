import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api-client';
import { EVENT_TYPE_LABELS } from '@/lib/constants';
import type { RecordEvent } from '@/types/session';

interface EventTimelineProps {
  sessionId: string;
  onGenerate: () => void;
}

export function EventTimeline({ sessionId, onGenerate }: EventTimelineProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['session-events', sessionId],
    queryFn: () =>
      api.get<{ events: RecordEvent[]; total: number }>(
        `/sessions/${sessionId}/events`
      ),
  });

  const events = data?.events ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Recorded Events</h3>
          <p className="text-sm text-muted-foreground">
            {events.length} events captured. Review and trim before generating
            workflow.
          </p>
        </div>
        <Button onClick={onGenerate} disabled={events.length < 3}>
          Generate Workflow
        </Button>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading events...</p>}

      <ScrollArea className="h-[60vh]">
        <div className="space-y-2 pr-4">
          {events.map((ev) => (
            <EventCard key={ev.seq} event={ev} sessionId={sessionId} />
          ))}
        </div>
      </ScrollArea>

      {events.length < 3 && events.length > 0 && (
        <p className="text-sm text-destructive">
          At least 3 events are needed to generate a workflow.
        </p>
      )}
    </div>
  );
}

function EventCard({
  event,
  sessionId,
}: {
  event: RecordEvent;
  sessionId: string;
}) {
  const label = EVENT_TYPE_LABELS[event.event_type] ?? event.event_type;
  const time = new Date(event.timestamp).toLocaleTimeString();

  // Extract screenshot filename from path
  const screenshotFilename = event.screenshot_path
    ? event.screenshot_path.split(/[/\\]/).pop()
    : null;

  return (
    <Card className="flex items-start gap-3 p-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-mono">
        {event.seq}
      </div>

      {screenshotFilename && (
        <img
          src={`/api/v1/sessions/${sessionId}/screenshots/${screenshotFilename}`}
          alt={`Event ${event.seq}`}
          className="h-16 w-24 shrink-0 rounded border object-cover"
          loading="lazy"
        />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {label}
          </Badge>
          <span className="text-xs text-muted-foreground">{time}</span>
        </div>
        <div className="mt-1 text-sm text-muted-foreground truncate">
          {formatEventDetail(event)}
        </div>
      </div>
    </Card>
  );
}

function formatEventDetail(ev: RecordEvent): string {
  switch (ev.event_type) {
    case 'click':
      return `${ev.button ?? 'left'} click at (${ev.x}, ${ev.y})`;
    case 'double_click':
      return `double click at (${ev.x}, ${ev.y})`;
    case 'type':
      return `typed: "${String(ev.text ?? '').slice(0, 50)}"`;
    case 'key':
      return `keys: ${(ev.keys as string[])?.join(' + ') ?? ''}`;
    case 'scroll':
      return `scroll ${ev.direction} x${ev.amount}`;
    case 'drag':
      return `drag (${ev.start_x},${ev.start_y}) → (${ev.end_x},${ev.end_y})`;
    case 'app_launch':
      return `launched: ${ev.app_name}`;
    case 'window_change':
      return `window: ${ev.window_title}`;
    default:
      return '';
  }
}
