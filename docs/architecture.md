# Architecture

## System Overview
The backend is built with FastAPI, PostgreSQL, and MediaMTX.
It uses an asynchronous architecture for both web requests (FastAPI) and event processing (AIOKafka).

## Components
- **API Gateway**: Kong
- **Database**: PostgreSQL with PostGIS
- **Message Broker**: Kafka
- **Object Storage**: MinIO
- **Media Server**: MediaMTX
