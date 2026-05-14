// MCP heartbeat client.
//
// Posts the running MCP server's identity + version to the backend's
// /agents/heartbeat endpoint every HEARTBEAT_INTERVAL ms so that the
// Agents tab in the SOAS UI lists this MCP instance alongside the
// Python services. Best-effort — errors are logged and swallowed.

const HEARTBEAT_INTERVAL = 30_000; // 30s

function resolveAgentId(role) {
  const env = (process.env.SOAS_AGENT_ID || "").trim();
  if (/^[a-z][a-z0-9_]*_[0-9]{1,6}$/.test(env)) return env;
  // Fall back to hostname-derived id, matching the Python convention.
  const host = (process.env.HOSTNAME || "").split(".")[0].replace(/^soas[-_]/, "");
  const m = host.match(/^(\w+?)[-_]?(\d+)?$/);
  if (m && m[1]) return `${m[1].toLowerCase()}_${(m[2] || "001").padStart(3, "0")}`;
  return `${role}_001`;
}

export function startHeartbeat({ apiUrl }) {
  const role = process.env.SOAS_AGENT_ROLE || "mcp";
  const agentId = resolveAgentId(role);
  const version = process.env.SOAS_VERSION || "0.1.0";
  const bootTs = Date.now();

  async function tick() {
    const body = {
      agenttype_id: agentId,
      role,
      version,
      uptime_seconds: Math.floor((Date.now() - bootTs) / 1000),
      mem_rss_bytes: process.memoryUsage().rss,
      instance_id: process.env.HOSTNAME || agentId,
    };
    try {
      const res = await fetch(`${apiUrl}/agents/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        console.warn(`[heartbeat] backend returned ${res.status}`);
      }
    } catch (err) {
      // backend may not be up yet; quiet retry on next tick
      console.warn(`[heartbeat] failed: ${err.message}`);
    }
  }

  // Fire immediately then on an interval.
  tick();
  const handle = setInterval(tick, HEARTBEAT_INTERVAL);
  return () => clearInterval(handle);
}
