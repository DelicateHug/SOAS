#!/bin/bash
# Generate RS256 key pair for JWT signing
set -e

SECRETS_DIR="$(dirname "$0")/../secrets"
mkdir -p "$SECRETS_DIR"

echo "Generating RSA key pair for JWT..."
openssl genrsa -out "$SECRETS_DIR/jwt_private.pem" 2048
openssl rsa -in "$SECRETS_DIR/jwt_private.pem" -pubout -out "$SECRETS_DIR/jwt_public.pem"

echo "Keys generated:"
echo "  Private: $SECRETS_DIR/jwt_private.pem"
echo "  Public:  $SECRETS_DIR/jwt_public.pem"
echo ""
echo "IMPORTANT: Do not commit these files to git!"
