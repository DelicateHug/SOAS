---
title: "User Secrets"
slug: "user-secrets-guide"
icon: "key"
tags: ["guide", "secrets"]
---

# User Secrets

User Secrets store sensitive credentials (API keys, tokens, passwords) encrypted at rest.

## How It Works

- Each user has their own set of secrets
- Secrets are encrypted using AES before storage
- At automation runtime, secrets are decrypted and made available via the **Get User Secret** node
- Secrets marked as **Sensitive** cannot have their values retrieved via the API

## Managing Secrets

Navigate to **My Secrets** to:
- **Create** - Add a new secret with a name, description, and value
- **Update** - Change the value or description
- **Delete** - Remove a secret permanently

## Using Secrets in Automations

1. Create a secret (e.g., `VIRUSTOTAL_API_KEY`)
2. In your automation, add a **Get User Secret** node
3. Select the secret name from the dropdown
4. The decrypted value is available on the output port

## Admin View

Administrators can view all users' secret names (not values) at **Admin > User Secrets**.
