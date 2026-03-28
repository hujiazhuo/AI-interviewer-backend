#!/bin/bash

app_env=${1:-development}

# Prefer activating Python virtual environment if present
if [ -f "bin/activate" ]; then
    . bin/activate
fi

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Load local env files (secrets), if present
if [ -f ".env.local" ]; then
    set -a
    . ./.env.local
    set +a
elif [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

export PORT="${APP_PORT:-3000}"

# Development environment commands
dev_commands() {
    echo "Running development environment commands..."
    python3 hello.py
}

# Production environment commands
prod_commands() {
    echo "Running production environment commands..."
    python3 hello.py
}

# Decide environment based on argument
if [ "$app_env" = "production" ] || [ "$app_env" = "prod" ] ; then
    echo "Production environment detected"
    prod_commands
else
    echo "Development environment detected"
    dev_commands
fi
