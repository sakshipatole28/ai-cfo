import "./styles.css";

import {
  createBrowserHistory,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
  useRouterState,
} from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";

import { AppShell } from "@/components/shell/AppShell";
import { TooltipProvider } from "@/components/ui";
import { Client360 } from "@/pages/Client360";
import { Clients } from "@/pages/Clients";
import { ReviewInbox } from "@/pages/ReviewInbox";
import { Audit, Consent, DataInbox, Knowledge, Reports, Settings } from "@/pages/Secondary";
import { Today } from "@/pages/Today";
import { AppProvider, useApp } from "@/state/app";

function Root() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { theme } = useApp();
  return (
    <>
      {path === "/consent" ? <Outlet /> : <AppShell />}
      <Toaster position="bottom-right" theme={theme} richColors={false} closeButton toastOptions={{ className: "!font-sans" }} offset={{ bottom: 80 }} mobileOffset={{ bottom: 84 }} />
    </>
  );
}

const rootRoute = createRootRoute({ component: Root });
const todayRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Today });
const clientsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/clients", component: Clients });
const client360Route = createRoute({ getParentRoute: () => rootRoute, path: "/clients/$clientId", component: Client360 });
const reviewInboxRoute = createRoute({ getParentRoute: () => rootRoute, path: "/review", component: ReviewInbox });
const dataInboxRoute = createRoute({ getParentRoute: () => rootRoute, path: "/data", component: DataInbox });
const reportsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/reports", component: Reports });
const knowledgeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/knowledge", component: Knowledge });
const auditRoute = createRoute({ getParentRoute: () => rootRoute, path: "/audit", component: Audit });
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/settings", component: Settings });
const consentRoute = createRoute({ getParentRoute: () => rootRoute, path: "/consent", component: Consent });

const routeTree = rootRoute.addChildren([
  todayRoute,
  clientsRoute,
  client360Route,
  reviewInboxRoute,
  dataInboxRoute,
  reportsRoute,
  knowledgeRoute,
  auditRoute,
  settingsRoute,
  consentRoute,
]);

// The shareable preview runs inside a sandboxed frame, so it keeps routes in memory.
const router = createRouter({
  routeTree,
  history: import.meta.env.MODE === "preview" ? createMemoryHistory({ initialEntries: ["/"] }) : createBrowserHistory(),
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider>
      <TooltipProvider delayDuration={250}>
        <RouterProvider router={router} />
      </TooltipProvider>
    </AppProvider>
  </StrictMode>,
);
