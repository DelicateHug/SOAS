/** Extension identifier */
export const EXTENSION_ID = "soas";

/** Secret storage keys */
export const SECRET_KEYS = {
  ACCESS_TOKEN: "soas.accessToken",
  REFRESH_TOKEN: "soas.refreshToken",
} as const;

/** Global state keys */
export const STATE_KEYS = {
  ACTIVE_TEAM_ID: "soas.activeTeamId",
  ACTIVE_TEAM_NAME: "soas.activeTeamName",
  INCIDENT_FILTERS: "soas.incidentFilters",
  CASE_FILTERS: "soas.caseFilters",
  EXECUTION_FILTERS: "soas.executionFilters",
} as const;

/** Context keys set via vscode.commands.executeCommand('setContext', ...) */
export const CONTEXT_KEYS = {
  IS_AUTHENTICATED: "soas.isAuthenticated",
  IS_ADMIN: "soas.isAdmin",
  GRAPH_EDITOR_ACTIVE: "soas.graphEditorActive",
  DEV_MODE: "soas.devMode",
} as const;

/** View IDs matching package.json */
export const VIEW_IDS = {
  WELCOME: "soas-welcome",
  INCIDENTS: "soas-incidents",
  CASES: "soas-cases",
  AUTOMATIONS: "soas-automations",
  WIKI: "soas-wiki",
  EXECUTIONS: "soas-executions",
  ISSUES: "soas-issues",
  TEAMS: "soas-teams",
  ADMIN: "soas-admin",
} as const;

/** PostMessage types for webview ↔ extension host communication */
export const MSG = {
  // API bridge
  API_REQUEST: "api-request",
  API_RESPONSE: "api-response",
  // WebSocket bridge
  WS_OPEN: "ws-open",
  WS_CLOSE: "ws-close",
  WS_SEND: "ws-send",
  WS_MESSAGE: "ws-message",
  WS_ERROR: "ws-error",
  WS_CONNECTED: "ws-connected",
  WS_DISCONNECTED: "ws-disconnected",
  // Panel lifecycle
  PANEL_INIT: "panel-init",
  PANEL_READY: "panel-ready",
  // Graph editor specific
  GRAPH_LOAD: "graph-load",
  GRAPH_STATE: "graph-state",
  // Wiki editor specific
  WIKI_STATE: "wiki-state",
} as const;
