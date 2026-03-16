/**
 * Webview entry point.
 * Reads the panel type from the extension host via postMessage and renders the correct app.
 * Installs the WebSocket bridge before React mounts.
 */

import { Component, StrictMode, useEffect, useState, type ReactNode, type ErrorInfo } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/queryClient";
import { installWebSocketBridge } from "./lib/WebSocketBridge";
import { getVsCodeApi } from "./vscode";

// Panel apps (lazy imports to catch errors per-panel)
import { GraphEditorApp } from "./panels/GraphEditorApp";
import { WikiEditorApp } from "./panels/WikiEditorApp";
import { DashboardApp } from "./panels/DashboardApp";
import { MonitoringApp } from "./panels/MonitoringApp";
import { IncidentDetailApp } from "./panels/IncidentDetailApp";
import { CaseDetailApp } from "./panels/CaseDetailApp";
import { ExecutionOutputApp } from "./panels/ExecutionOutputApp";
import { AdminApp } from "./panels/AdminApp";

import "./styles/index.css";

// Install WebSocket bridge before React
installWebSocketBridge();

// Error boundary to catch render errors and show them visibly
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[SOAS Webview] Render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 20, color: "var(--vscode-errorForeground, #f44)", fontFamily: "var(--vscode-font-family)", fontSize: 13 }}>
          <h3 style={{ marginBottom: 8 }}>SOAS Panel Error</h3>
          <pre style={{ whiteSpace: "pre-wrap", background: "var(--vscode-textBlockQuote-background, #1e1e1e)", padding: 12, borderRadius: 4 }}>
            {this.state.error.message}
            {"\n\n"}
            {this.state.error.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  const [panelType, setPanelType] = useState<string | null>(null);
  const [initData, setInitData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    console.log("[SOAS Webview] App mounted, sending panel-ready");

    // Signal to extension host that we're ready
    getVsCodeApi().postMessage({ type: "panel-ready" });

    // Listen for init data
    const handler = (event: MessageEvent) => {
      const msg = event.data;
      console.log("[SOAS Webview] Received message:", msg.type, msg);
      if (msg.type === "panel-init") {
        setPanelType(msg.panelType);
        setInitData(msg.data || {});
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  if (!panelType) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--vscode-foreground)" }}>
        Loading...
      </div>
    );
  }

  console.log("[SOAS Webview] Rendering panel:", panelType, "with data:", initData);

  switch (panelType) {
    case "graphEditor":
      return <GraphEditorApp automationId={initData?.automationId as string} />;
    case "wikiEditor":
      return <WikiEditorApp pageId={initData?.pageId as string} slug={initData?.slug as string} />;
    case "dashboard":
      return <DashboardApp />;
    case "monitoring":
      return <MonitoringApp />;
    case "incidentDetail":
      return <IncidentDetailApp incidentId={initData?.incidentId as string} />;
    case "caseDetail":
      return <CaseDetailApp caseId={initData?.caseId as string} />;
    case "executionOutput":
      return <ExecutionOutputApp executionId={initData?.executionId as string} />;
    default:
      // Admin panels all start with "admin"
      if (panelType.startsWith("admin")) {
        return <AdminApp adminPanel={panelType} />;
      }
      return <div style={{ padding: 20, color: "var(--vscode-foreground)" }}>Unknown panel type: {panelType}</div>;
  }
}

// Global error handler for uncaught errors
window.addEventListener("error", (event) => {
  console.error("[SOAS Webview] Uncaught error:", event.error);
  const root = document.getElementById("root");
  if (root && !root.hasChildNodes()) {
    root.innerHTML = `<div style="padding:20px;color:#f44;font-size:13px"><b>SOAS Error:</b><pre>${event.error?.stack || event.message}</pre></div>`;
  }
});

const root = createRoot(document.getElementById("root")!);
root.render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>
);
