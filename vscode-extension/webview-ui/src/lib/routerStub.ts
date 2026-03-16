/**
 * Stub for react-router-dom in webview context.
 * Webviews don't have URL routing — data is passed via postMessage.
 * This provides no-op implementations of the hooks used by frontend components.
 */

import { useCallback } from "react";

export function useParams<T extends Record<string, string | undefined>>(): T {
  // Params are provided via panel init data, not URL
  return {} as T;
}

export function useNavigate() {
  return useCallback((_to: string | number) => {
    // Navigation in webviews is handled by the extension host
    console.warn("Navigation not supported in webview context");
  }, []);
}

export function useSearchParams(): [URLSearchParams, (params: URLSearchParams) => void] {
  return [new URLSearchParams(), () => {}];
}

export function useLocation() {
  return { pathname: "/", search: "", hash: "", state: null, key: "default" };
}

export function Link(props: { to: string; children: React.ReactNode; [key: string]: unknown }) {
  return props.children;
}

export function NavLink(props: { to: string; children: React.ReactNode; [key: string]: unknown }) {
  return props.children;
}

export function Outlet() {
  return null;
}

export function Navigate(_props: { to: string; replace?: boolean }) {
  return null;
}

export function Routes(props: { children: React.ReactNode }) {
  return props.children;
}

export function Route(_props: { path: string; element: React.ReactNode }) {
  return null;
}

export function BrowserRouter(props: { children: React.ReactNode }) {
  return props.children;
}

export function MemoryRouter(props: { children: React.ReactNode }) {
  return props.children;
}
