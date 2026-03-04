/**
 * Default code templates shown when creating a new code block.
 * Showcases all available APIs: inputs/outputs, incident vars, SOAS vars, globals.
 */

export const EXAMPLE_TEMPLATES: Record<string, string> = {
  python: `# ── Code Block ────────────────────────────────────────
# Available variables:
#   inputs   - dict of values from connected input ports
#   outputs  - dict to set values for output ports
#   globals  - persistent store across nodes
#
# Incident functions (available when run with an incident):
#   get_incident_var("name", default=None)
#   set_incident_var("name", value)
#   get_incident_data()  -> dict of all incident metadata
#
# SOAS variable functions (app-level variables):
#   get_soas_var("name", default=None)
#   set_soas_var("name", value)
# ──────────────────────────────────────────────────────

# Read from input ports
value = inputs.get("value")

# Your logic here
result = value

# Write to output ports
outputs["result"] = result
`,

  javascript: `// ── Code Block ────────────────────────────────────────
// Available variables:
//   inputs   - object with values from connected input ports
//   outputs  - object to set values for output ports
// ──────────────────────────────────────────────────────

// Read from input ports
const value = inputs["value"];

// Your logic here
const result = value;

// Write to output ports
outputs["result"] = result;
`,

  bash: `#!/bin/bash
# ── Code Block ────────────────────────────────────────
# Input values are available as environment variables:
#   $INPUT_VALUE - value from the "value" input port
#
# To set output, echo to stdout (captured as "result")
# ──────────────────────────────────────────────────────

echo "$INPUT_VALUE"
`,
};
