#!/usr/bin/env bash
set -e

echo "🚀 Starting Event-Driven Layered Microservices (MQTT + TimescaleDB)..."
echo "📦 Building containers..."

docker compose up --build -d

echo ""
echo "✅ All services running!"
echo "--------------------------------------------------------"
echo "🌐 Frontend Dashboard:       http://localhost:3000"
echo "🚪 API Gateway:              http://localhost:8000"
echo "📖 API Gateway Docs:         http://localhost:8000/docs"
echo "📡 Sensor Service Docs:      http://localhost:8003/docs"
echo "⚡ Analytics Consumer Docs:   http://localhost:8004/docs"
echo "👤 User Service Docs:        http://localhost:8001/docs"
echo "🛍️ Product Service Docs:     http://localhost:8002/docs"
echo "📡 Eclipse Mosquitto (MQTT): localhost:1883 (TCP) & 9001 (WS)"
echo "⏱️ TimescaleDB:              localhost:5432 (app_db)"
echo "--------------------------------------------------------"
