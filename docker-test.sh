#!/bin/bash
echo "🚀 Testing Docker Setup..."
echo ""
echo "1. Stopping existing containers..."
docker-compose down -v

echo ""
echo "2. Building fresh images..."
docker-compose build --no-cache

echo ""
echo "3. Starting services..."
docker-compose up -d

echo ""
echo "4. Waiting for services to be healthy..."
sleep 10

echo ""
echo "5. Checking container status..."
docker-compose ps

echo ""
echo "6. Checking web logs..."
docker-compose logs web | tail -20

echo ""
echo "✅ Setup complete! Access app at http://localhost:8000"
echo "Default login: admin / admin"
