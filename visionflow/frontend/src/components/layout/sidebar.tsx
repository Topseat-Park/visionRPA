import { Link, useMatchRoute } from '@tanstack/react-router';
import {
  Home,
  Mic,
  Play,
  History,
  Clock,
  Settings,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/' as const, label: '워크플로우', icon: Home },
  { to: '/record' as const, label: '녹화', icon: Mic },
  { to: '/runs' as const, label: '실행 이력', icon: History },
  { to: '/schedules' as const, label: '스케줄', icon: Clock },
  { to: '/settings' as const, label: '설정', icon: Settings },
];

export function Sidebar() {
  const matchRoute = useMatchRoute();

  return (
    <aside className="flex h-full w-56 flex-col border-r bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <Play className="h-5 w-5 text-primary" />
        <span className="text-lg font-semibold">VisionFlow</span>
      </div>

      <nav className="flex-1 space-y-1 px-2 py-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => {
          const isActive = matchRoute({ to, fuzzy: true });
          return (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                  : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
