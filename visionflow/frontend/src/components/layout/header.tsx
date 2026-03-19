import { AgentStatusIndicator } from '@/components/shared/agent-status';

export function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-6">
      <h1 className="text-sm font-medium text-muted-foreground">대시보드</h1>
      <AgentStatusIndicator />
    </header>
  );
}
