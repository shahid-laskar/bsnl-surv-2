#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# KONG_ADMIN_URL="http://192.168.220.31:8001"



# Build KONG_ADMIN_URL using HOST_IP from .env
KONG_ADMIN_URL="http://kong:8001"

echo -e "${GREEN}=== COMPLETE KONG SETUP WITH JWT + S3 DUAL AUTHENTICATION ===${NC}"

# Function to check if command succeeded
check_response() {
    local response="$1"
    local name="$2"
    local id=$(echo "$response" | jq -r '.id // empty')
    
    if [ -z "$id" ] || [ "$id" == "null" ]; then
        echo -e "${RED}Failed to create $name:${NC}"
        echo "$response" | jq '.'
        return 1
    else
        echo -e "${GREEN}✓ Created $name: $id${NC}"
        return 0
    fi
}

# Function to add plugin to route
add_plugin_to_route() {
    local route_id="$1"
    local route_name="$2"
    local plugin_name="$3"
    local plugin_config="$4"
    
    echo "Adding $plugin_name plugin to $route_name..."
    PLUGIN_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/routes/$route_id/plugins" \
      -H "Content-Type: application/json" \
      -d "$plugin_config")
    
    PLUGIN_ID=$(echo "$PLUGIN_RESPONSE" | jq -r '.id')
    if [ "$PLUGIN_ID" == "null" ] || [ -z "$PLUGIN_ID" ]; then
        echo -e "${RED}$plugin_name plugin failed for $route_name:${NC} $(echo "$PLUGIN_RESPONSE" | jq -r '.message // .')"
        return 1
    else
        echo -e "${GREEN}✓ $plugin_name plugin added to $route_name: $PLUGIN_ID${NC}"
        return 0
    fi
}

echo -e "${YELLOW}1. Complete cleanup of existing configuration...${NC}"

# Clean up existing routes
echo "Cleaning existing routes..."
EXISTING_ROUTES=$(curl -s "$KONG_ADMIN_URL/routes" | jq -r '.data[] | select(.paths[]? | test("mediamtx|minio|stream|recordings")) | .id')
for route_id in $EXISTING_ROUTES; do
    if [ ! -z "$route_id" ]; then
        echo "Deleting route: $route_id"
        curl -s -X DELETE "$KONG_ADMIN_URL/routes/$route_id"
    fi
done

# Clean up existing services
echo "Cleaning existing services..."
EXISTING_SERVICES=$(curl -s "$KONG_ADMIN_URL/services" | jq -r '.data[] | select(.name | test("mediamtx|minio")) | .id')
for service_id in $EXISTING_SERVICES; do
    if [ ! -z "$service_id" ]; then
        echo "Deleting service: $service_id"
        curl -s -X DELETE "$KONG_ADMIN_URL/services/$service_id"
    fi
done

# Clean up existing consumers
echo "Cleaning existing consumers..."
EXISTING_CONSUMERS=$(curl -s "$KONG_ADMIN_URL/consumers" | jq -r '.data[] | select(.username | test("cctv")) | .id')
for consumer_id in $EXISTING_CONSUMERS; do
    if [ ! -z "$consumer_id" ]; then
        echo "Deleting consumer: $consumer_id"
        curl -s -X DELETE "$KONG_ADMIN_URL/consumers/$consumer_id"
    fi
done

sleep 2

echo -e "${YELLOW}2. Creating JWT Consumer and Credentials...${NC}"
CONSUMER_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/consumers/" \
  --data "username=cctv-client")

if check_response "$CONSUMER_RESPONSE" "consumer"; then
    echo "Creating JWT credentials..."
    JWT_CRED_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/consumers/cctv-client/jwt" \
      --data "key=cctv@Bsnl" \
      --data "secret=Bsnl@9876" \
      --data "algorithm=HS256")
    
    check_response "$JWT_CRED_RESPONSE" "JWT credentials"
fi

echo -e "${YELLOW}3. Creating Services...${NC}"

# MediaMTX Service
echo "Creating MediaMTX service..."
MEDIAMTX_SERVICE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/" \
  --data "name=mediamtx-service" \
  --data "url=http://mediamtx:9997")

check_response "$MEDIAMTX_SERVICE_RESPONSE" "MediaMTX service"

# MinIO Console Service (for web UI and admin operations)
echo "Creating MinIO Console service..."
MINIO_CONSOLE_SERVICE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/" \
  --data "name=minio-console" \
  --data "url=http://minio:9001")

check_response "$MINIO_CONSOLE_SERVICE_RESPONSE" "MinIO Console service"

# MinIO S3 API Service (for S3 operations with dual authentication)
echo "Creating MinIO S3 API service..."
MINIO_S3_SERVICE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/" \
  --data "name=minio-s3" \
  --data "url=http://minio:9000")

check_response "$MINIO_S3_SERVICE_RESPONSE" "MinIO S3 API service"

echo -e "${YELLOW}4. Creating Routes...${NC}"

# MediaMTX API Route (with JWT authentication)
echo "Creating MediaMTX API route..."
MEDIAMTX_ROUTE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/mediamtx-service/routes" \
  --data "name=mediamtx-api" \
  --data "paths[]=/api/mediamtx" \
  --data "methods[]=GET" \
  --data "methods[]=POST" \
  --data "methods[]=PUT" \
  --data "methods[]=DELETE" \
  --data "methods[]=OPTIONS" \
  --data "methods[]=HEAD" \
  --data "strip_path=true")

MEDIAMTX_ROUTE_ID=$(echo "$MEDIAMTX_ROUTE_RESPONSE" | jq -r '.id')
check_response "$MEDIAMTX_ROUTE_RESPONSE" "MediaMTX API route"

# MinIO Console Route (with JWT authentication)
echo "Creating MinIO Console route..."
MINIO_CONSOLE_ROUTE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/minio-console/routes" \
  --data "name=minio-console-api" \
  --data "paths[]=/api/minio-console" \
  --data "methods[]=GET" \
  --data "methods[]=POST" \
  --data "methods[]=PUT" \
  --data "methods[]=DELETE" \
  --data "methods[]=OPTIONS" \
  --data "methods[]=HEAD" \
  --data "strip_path=true")

MINIO_CONSOLE_ROUTE_ID=$(echo "$MINIO_CONSOLE_ROUTE_RESPONSE" | jq -r '.id')
check_response "$MINIO_CONSOLE_ROUTE_RESPONSE" "MinIO Console route"

# MinIO S3 API Route (WITH JWT + S3 DUAL AUTHENTICATION)
echo "Creating MinIO S3 API route with dual authentication..."
MINIO_S3_ROUTE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/minio-s3/routes" \
  --data "name=minio-s3-api" \
  --data "paths[]=/api/minio-s3" \
  --data "strip_path=true" \
  --data "preserve_host=false")

MINIO_S3_ROUTE_ID=$(echo "$MINIO_S3_ROUTE_RESPONSE" | jq -r '.id')
check_response "$MINIO_S3_ROUTE_RESPONSE" "MinIO S3 API route"

# HLS Stream Route (no authentication needed for streaming)
echo "Creating HLS stream route..."
HLS_ROUTE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/mediamtx-service/routes" \
  --data "name=hls-streams" \
  --data "paths[]=/stream/hls" \
  --data "methods[]=GET" \
  --data "methods[]=OPTIONS" \
  --data "strip_path=true")

HLS_ROUTE_ID=$(echo "$HLS_ROUTE_RESPONSE" | jq -r '.id')
check_response "$HLS_ROUTE_RESPONSE" "HLS stream route"

echo -e "${YELLOW}5. Adding plugins to routes...${NC}"

# JWT Plugin for MediaMTX API
if [ ! -z "$MEDIAMTX_ROUTE_ID" ] && [ "$MEDIAMTX_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MEDIAMTX_ROUTE_ID" "MediaMTX API" "JWT" '{
        "name": "jwt",
        "config": {
            "secret_is_base64": false,
            "key_claim_name": "iss",
            "claims_to_verify": ["exp"]
        }
    }'
fi

# JWT Plugin for MinIO Console
if [ ! -z "$MINIO_CONSOLE_ROUTE_ID" ] && [ "$MINIO_CONSOLE_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MINIO_CONSOLE_ROUTE_ID" "MinIO Console" "JWT" '{
        "name": "jwt",
        "config": {
            "secret_is_base64": false,
            "key_claim_name": "iss",
            "claims_to_verify": ["exp"]
        }
    }'
fi

# JWT Plugin for MinIO S3 API (DUAL AUTHENTICATION - STEP 1)
if [ ! -z "$MINIO_S3_ROUTE_ID" ] && [ "$MINIO_S3_ROUTE_ID" != "null" ]; then
    echo -e "${YELLOW}Setting up DUAL AUTHENTICATION for MinIO S3...${NC}"
    
    # Step 1: JWT Plugin - validates Kong access
    add_plugin_to_route "$MINIO_S3_ROUTE_ID" "MinIO S3 API" "JWT" '{
        "name": "jwt",
        "config": {
            "secret_is_base64": false,
            "key_claim_name": "iss",
            "claims_to_verify": ["exp"]
        }
    }'
    
    # Step 2: Request Transformer - Clean ALL problematic headers for S3 signature validation
    echo -e "${YELLOW}⚠️  CRITICAL: Removing ALL headers that interfere with S3 signature validation...${NC}"
    add_plugin_to_route "$MINIO_S3_ROUTE_ID" "MinIO S3 API" "Request-Transformer" '{
        "name": "request-transformer",
        "config": {
            "remove": {
                "headers": [
                    "Authorization",
                    "authorization",
                    "origin",
                    "referer",
                    "accept-language",
                    "accept-encoding",
                    "priority",
                    "sec-fetch-dest",
                    "sec-fetch-mode",
                    "sec-fetch-site",
                    "user-agent",
                    "Via",
                    "via",
                    "X-Forwarded-For",
                    "x-forwarded-for",
                    "X-Real-Ip",
                    "x-real-ip",
                    "X-Forwarded-Host",
                    "x-forwarded-host",
                    "X-Forwarded-Port",
                    "x-forwarded-port",
                    "X-Forwarded-Proto",
                    "x-forwarded-proto",
                    "X-Forwarded-Path",
                    "x-forwarded-path",
                    "X-Forwarded-Prefix",
                    "x-forwarded-prefix",
                    "X-Consumer-Id",
                    "x-consumer-id",
                    "X-Consumer-Username",
                    "x-consumer-username",
                    "X-Credential-Identifier",
                    "x-credential-identifier",
                    "X-Kong-Request-Id",
                    "x-kong-request-id",
                    "Connection",
                    "connection",
                    "Cache-Control",
                    "cache-control",
                    "Pragma",
                    "pragma",
                    "Upgrade-Insecure-Requests",
                    "upgrade-insecure-requests"
                ]
            },
            "replace": {
                "headers": [
                    "Host:minio:9000"
                ]
            }
        }
    }'
fi

# CORS Plugin for MediaMTX API
if [ ! -z "$MEDIAMTX_ROUTE_ID" ] && [ "$MEDIAMTX_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MEDIAMTX_ROUTE_ID" "MediaMTX API" "CORS" '{
        "name": "cors",
        "config": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            "headers": ["Accept", "Accept-Version", "Content-Length", "Content-MD5", "Content-Type", "Date", "Authorization"],
            "exposed_headers": ["*"],
            "credentials": true,
            "max_age": 3600
        }
    }'
fi

# CORS Plugin for MinIO Console
if [ ! -z "$MINIO_CONSOLE_ROUTE_ID" ] && [ "$MINIO_CONSOLE_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MINIO_CONSOLE_ROUTE_ID" "MinIO Console" "CORS" '{
        "name": "cors",
        "config": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            "headers": ["Accept", "Accept-Version", "Content-Length", "Content-MD5", "Content-Type", "Date", "Authorization"],
            "exposed_headers": ["*"],
            "credentials": true,
            "max_age": 3600
        }
    }'
fi

# CORS Plugin for MinIO S3 API (supports dual auth headers)
if [ ! -z "$MINIO_S3_ROUTE_ID" ] && [ "$MINIO_S3_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MINIO_S3_ROUTE_ID" "MinIO S3 API" "CORS" '{
        "name": "cors",
        "config": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            "headers": ["Accept", "Accept-Version", "Content-Length", "Content-Type", "Date", "Range", "Authorization", "If-Modified-Since", "If-Unmodified-Since", "If-Match", "If-None-Match"],
            "exposed_headers": ["ETag", "Content-Range", "Accept-Ranges", "Content-Length", "Last-Modified", "X-Amz-Request-Id", "X-Amz-Id-2"],
            "credentials": true,
            "max_age": 3600
        }
    }'
fi

# CORS Plugin for HLS Streams (no authentication)
if [ ! -z "$HLS_ROUTE_ID" ] && [ "$HLS_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$HLS_ROUTE_ID" "HLS Streams" "CORS" '{
        "name": "cors",
        "config": {
            "origins": ["*"],
            "methods": ["GET", "OPTIONS"],
            "headers": ["Accept", "Accept-Version", "Content-Length", "Content-Type", "Date"],
            "exposed_headers": ["*"],
            "credentials": true,
            "max_age": 3600
        }
    }'
fi

# Request Transformer for MinIO Console (add Basic Auth for console access)
if [ ! -z "$MINIO_CONSOLE_ROUTE_ID" ] && [ "$MINIO_CONSOLE_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$MINIO_CONSOLE_ROUTE_ID" "MinIO Console" "Request-Transformer" '{
        "name": "request-transformer",
        "config": {
            "remove": {
                "headers": ["authorization"]
            },
            "add": {
                "headers": ["Authorization:Basic bWluaW9hZG1pbjptaW5pb2FkbWluMTIz"]
            }
        }
    }'
fi
# Add FastAPI API Service
echo "Creating FastAPI API service..."
FASTAPI_SERVICE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/" \
  --data "name=fastapi-api" \
  --data "url=http://fastapi:8000" \
  --data "path=/")

check_response "$FASTAPI_SERVICE_RESPONSE" "FastAPI API service"

# Add route for FastAPI API
echo "Creating FastAPI API route..."
FASTAPI_ROUTE_RESPONSE=$(curl -s -X POST "$KONG_ADMIN_URL/services/fastapi-api/routes" \
  --data "name=fastapi-api-route" \
  --data "paths[]=/api" \
  --data "strip_path=false")

FASTAPI_ROUTE_ID=$(echo "$FASTAPI_ROUTE_RESPONSE" | jq -r '.id')
check_response "$FASTAPI_ROUTE_RESPONSE" "FastAPI API route"

# Add JWT plugin to FastAPI API route
if [ ! -z "$FASTAPI_ROUTE_ID" ] && [ "$FASTAPI_ROUTE_ID" != "null" ]; then
    add_plugin_to_route "$FASTAPI_ROUTE_ID" "FastAPI API" "JWT" '{
        "name": "jwt",
        "config": {
            "secret_is_base64": false,
            "key_claim_name": "iss",
            "claims_to_verify": ["exp"]
        }
    }'
fi
