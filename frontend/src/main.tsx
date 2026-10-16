import "./styles.css";

import {
  createBrowserHistory,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";

import { AppShell } from "@/components/shell/AppShell";
import { TooltipProvider } from "@/components/ui";
import { Client360 } from "@/pages/Client360";
import { Clients } from "@/pages/Clients";
import { ReviewInbox } from "@/pages/ReviewInbox";
import { Access, Team } from "@/pages/Firm";
import { Knowledge } from "@/pages/Knowledge";
import { Portal } from "@/pages/Portal";
import { Audit, Consent, DataInbox, Reports, Settings } from "@/pages/Secondary";
import { SignIn } from "@/pages/SignIn";
import { Today } from "@/pages/Today";
import { AppProvider, useApp } from "@/state/app";

const PUBLIC = new Set(["/signin", "/consent"]);

/** Route guard: firm pages need a signed-in team member; the portal needs a signed-in client. */
function Root() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { theme, me, clientId } = useApp();
  const navigate = useNavigate();
  const isPublic = PUBLIC.has(path);
  const isPortal = path === "/portal";
  const allowed = isPublic || (isPortal ? !!clientId : !!me);

  useEffect(() => {
    if (!allowed) void navigate({ to: "/signin", replace: true });
  }, [allowed, navigate]);

  return (
    <>
      {allowed ? isPublic || isPortal ? <Outlet /> : <AppShell /> : null}
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
const signInRoute = createRoute({ getParentRoute: () => rootRoute, path: "/signin", component: SignIn });
const portalRoute = createRoute({ getParentRoute: () => rootRoute, path: "/portal", component: Portal });
const teamRoute = createRoute({ getParentRoute: () => rootRoute, path: "/team", component: Team });
const accessRoute = createRoute({ getParentRoute: () => rootRoute, path: "/access", component: Access });

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
  signInRoute,
  portalRoute,
  teamRoute,
  accessRoute,
]);

// The shareable preview runs inside a sandboxed frame, so it keeps routes in memory.
const router = createRouter({
  routeTree,
  history: import.meta.env.MODE === "preview" ? createMemoryHistory({ initialEntries: ["/signin"] }) : createBrowserHistory(),
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
