# SOAS MCP server — exposes the SOAS backend as MCP tools.
#
# Two entrypoints in this image:
#   * server.js       — streamable-HTTP transport on :8765 (the default for `start.ps1`)
#   * server-stdio.js — classic stdio transport for IDE integrations that prefer it
#
# Auth: the server reads a service token from $SOAS_TOKEN_FILE (mounted) or $SOAS_TOKEN.
FROM node:22-alpine

WORKDIR /app

# Install deps in a separate layer so npm cache is reused across rebuilds.
COPY mcp/package.json ./package.json
RUN npm install --omit=dev --no-audit --no-fund

COPY mcp/src ./src

# Healthcheck endpoint backed by /healthz on the HTTPS server. Uses the mTLS client
# cert mounted at /run/mtls/mcp so the server-side `rejectUnauthorized` accepts it.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
  CMD node -e "const fs=require('fs');const{Agent}=require('undici');const a=new Agent({connect:{ca:fs.readFileSync('/run/mtls/ca/ca.crt'),cert:fs.readFileSync('/run/mtls/mcp/client.crt'),key:fs.readFileSync('/run/mtls/mcp/client.key')}});fetch('https://localhost:8765/healthz',{dispatcher:a}).then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

EXPOSE 8765

ENV NODE_ENV=production \
    SOAS_API_URL=https://backend:8000/api/v1 \
    EMBEDDING_SERVICE_URL=https://embeddings:8200 \
    MCP_HTTP_PORT=8765 \
    SOAS_TOKEN_FILE=/run/secrets/mcp_token \
    MTLS_DIR=/run/mtls

CMD ["node", "src/server.js"]
