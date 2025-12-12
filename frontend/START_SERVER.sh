#!/bin/bash

# SmartPlayFPL Frontend Startup Script
# Run this script to start the development server

echo "🚀 Starting SmartPlayFPL Frontend..."

# Navigate to frontend directory
cd "$(dirname "$0")"

# Kill any existing Next.js processes
echo "📋 Cleaning up existing processes..."
pkill -f "next dev" 2>/dev/null
sleep 2

# Update browserslist database (fixes autoprefixer issues)
echo "🔧 Updating browserslist database..."
npx update-browserslist-db@latest -y

# Try starting on port 3002 (avoiding permission issues)
echo "🌐 Starting server on port 3002..."
PORT=3002 npm run dev



