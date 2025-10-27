# pygeoapi ArcGIS MapServer proxy

This service runs an ArcGIS MapServer-compatible API using Docker Compose. Follow the steps below to build and start the service locally.

## Prerequisites
- Docker and Docker Compose installed on your system.

## Build and Start the Service

```sh
docker compose build --no-cache
docker compose up
```

## Access the Service

Once running, open your browser and go to:

http://localhost:5000/

The API should now be available at this address.
