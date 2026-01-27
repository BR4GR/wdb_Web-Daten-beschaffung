#!/bin/bash

# Load environment variables from .env file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

# Check required variables
if [ -z "$MONGO_API_PUBLIC_KEY" ] || [ -z "$MONGO_API_PRIVATE_KEY" ] || [ -z "$PROJECT_ID" ]; then
    echo "Error: Missing required environment variables"
    echo "Make sure .env contains: MONGO_API_PUBLIC_KEY, MONGO_API_PRIVATE_KEY, PROJECT_ID"
    exit 1
fi

# Get current public IP
IP=$(curl -s https://ipinfo.io/ip)

if [ -z "$IP" ]; then
    echo "Error: Could not determine public IP"
    exit 1
fi

echo "Adding IP $IP to MongoDB Atlas whitelist..."

# Add IP to Atlas whitelist
RESPONSE=$(curl -s -w "\n%{http_code}" -u "$MONGO_API_PUBLIC_KEY:$MONGO_API_PRIVATE_KEY" \
    --digest \
    -X POST \
    --header "Content-Type: application/json" \
    --data "[{\"ipAddress\": \"$IP\", \"comment\": \"Local dev $(date +%Y-%m-%d)\"}]" \
    "https://cloud.mongodb.com/api/atlas/v1.0/groups/$PROJECT_ID/accessList")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 201 ] || [ "$HTTP_CODE" -eq 200 ]; then
    echo "Successfully whitelisted IP: $IP"
elif echo "$BODY" | grep -q "ALREADY_EXISTS"; then
    echo "IP $IP is already whitelisted"
else
    echo "Failed to whitelist IP. HTTP $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
