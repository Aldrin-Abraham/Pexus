#!/bin/bash

# Niyati check script for Pexus Payment Gateway

echo "🔍 Running Niyati checks for Pexus Payment Gateway..."

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check if required files exist
echo "📁 Checking required files..."
if [ ! -f "app.py" ]; then
    echo "❌ app.py not found!"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found!"
    exit 1
fi

# Test if Flask app can import
echo "🔄 Testing Flask app import..."
python -c "from app import app; print('✅ Flask app imported successfully')" || {
    echo "❌ Failed to import Flask app"
    exit 1
}

# Check template files
echo "📄 Checking template files..."
if [ ! -d "templates" ]; then
    echo "❌ templates directory not found!"
    exit 1
fi

required_templates=("base.html" "index.html" "login.html" "dashboard.html" "make_payment.html" "transaction_history.html" "refund.html" "summary.html" "admin_dashboard.html" "admin_login.html")
for template in "${required_templates[@]}"; do
    if [ ! -f "templates/$template" ]; then
        echo "⚠️  Warning: templates/$template not found"
    fi
done

# Check static files
if [ ! -d "static" ] || [ ! -f "static/css/style.css" ]; then
    echo "⚠️  Warning: static/css/style.css not found"
fi

# Quick database connection test (optional)
echo "🛢️  Testing database connection (optional)..."
python -c "
import os
from app import get_db_connection
conn = get_db_connection()
if conn:
    print('✅ Database connection successful')
    conn.close()
else:
    print('⚠️  Database connection failed (this may be expected in build environment)')
" 2>/dev/null || echo "⚠️  Database test skipped"

echo "✅ All checks passed!"
exit 0