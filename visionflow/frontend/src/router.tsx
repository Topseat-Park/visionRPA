import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from '@tanstack/react-router';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';

// ── Root layout ────────────────────────────────────────
const rootRoute = createRootRoute({
  component: () => (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  ),
});

// ── Lazy imports ───────────────────────────────────────
// Pages are defined in separate files but mounted here
import { HomePage } from '@/pages/home';
import { RecordPage } from '@/pages/record';
import { WorkflowEditPage } from '@/pages/workflow-edit';
import { RunHistoryPage } from '@/pages/run-history';
import { RunMonitorPage } from '@/pages/run-monitor';
import { SchedulesPage } from '@/pages/schedules';
import { SettingsPage } from '@/pages/settings';

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomePage,
});

const recordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/record',
  component: RecordPage,
});

const workflowEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workflows/$workflowId',
  component: WorkflowEditPage,
});

const runsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runs',
  component: RunHistoryPage,
});

const runMonitorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runs/$runId',
  component: RunMonitorPage,
});

const schedulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/schedules',
  component: SchedulesPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  recordRoute,
  workflowEditRoute,
  runMonitorRoute,
  runsIndexRoute,
  schedulesRoute,
  settingsRoute,
]);

export const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
