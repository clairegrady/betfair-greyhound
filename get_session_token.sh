#!/bin/bash

# Get Betfair Session Token for Stream API
# NOTE: For PFX certificates, you need to extract .crt and .key first

PFX_PATH="/Users/clairegrady/RiderProjects/Betfair-pfx/betfair.pfx"
PFX_PASSWORD="HuaHin2024"
CERT_DIR="/tmp/betfair_certs"

USERNAME="clairegrady@me.com"
read -s -p "Betfair Password: " PASSWORD
echo ""

# Create temp directory for extracted certs
mkdir -p "$CERT_DIR"

echo "🔓 Extracting certificate from PFX..."

# Extract private key
openssl pkcs12 -in "$PFX_PATH" -nocerts -out "$CERT_DIR/key.pem" -nodes -passin pass:"$PFX_PASSWORD" 2>/dev/null

# Extract certificate
openssl pkcs12 -in "$PFX_PATH" -clcerts -nokeys -out "$CERT_DIR/cert.pem" -passin pass:"$PFX_PASSWORD" 2>/dev/null

if [ ! -f "$CERT_DIR/key.pem" ] || [ ! -f "$CERT_DIR/cert.pem" ]; then
    echo "❌ Failed to extract certificate from PFX"
    exit 1
fi

echo "✅ Certificate extracted"
echo "🔐 Getting session token..."

RESPONSE=$(curl -s -X POST "https://identitysso-cert.betfair.com/api/certlogin" \
  --cert "$CERT_DIR/cert.pem" --key "$CERT_DIR/key.pem" \
  -d "username=$USERNAME&password=$PASSWORD")

# Extract token from JSON response
TOKEN=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('sessionToken', 'ERROR'))" 2>/dev/null)

# Cleanup temp files
rm -rf "$CERT_DIR"

if [ "$TOKEN" = "ERROR" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get session token"
    echo "Response: $RESPONSE"
    exit 1
fi

echo "✅ Session Token: $TOKEN"
echo ""
echo "Token expires in ~8-12 hours"
echo ""
echo "Now run:"
echo "cd /Users/clairegrady/RiderProjects/betfair/greyhound-simulated/lay_betting"
echo "source ../venv/bin/activate"
echo "python3 lay_position_1_triple_stream_test.py '$TOKEN'"
