#!/bin/bash

# Script pour lancer Odoo
# Usage: ./run_odoo.sh

# Kill all running Odoo instances
echo "Stopping all running Odoo instances..."
pkill -f "odoo-bin" || true
pkill -f "python.*odoo-bin" || true

# Wait a moment for processes to terminate
sleep 2

# Check if any Odoo processes are still running and force kill if necessary
if pgrep -f "odoo-bin" > /dev/null; then
    echo "Force killing remaining Odoo processes..."
    pkill -9 -f "odoo-bin" || true
    sleep 1
fi

echo "Starting Odoo..."
cd /Users/abdelkader/odoo-dev/odoo && source venv/bin/activate && python3 odoo-bin --config=myodoo.cfg

