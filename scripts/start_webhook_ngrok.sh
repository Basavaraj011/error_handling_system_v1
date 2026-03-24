#!/usr/bin/env bash
# chmod +x scripts/start_webhook_ngrok.sh
# ./scripts/start_webhook_ngrok.sh

PORT=3978

# Determine project root (folder above /scripts)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# PROJECT_ROOT="C:/Users/bsulla01/OneDrive - dentsu/Documents/basav/AI/SelfHealingSystem/error-healing-system-repo/error_handling_system_webhook"

echo "Starting Flask webhook in new Git Bash window..."
start "" "C:/Program Files/Git/bin/bash.exe" -c "cd '$PROJECT_ROOT'; python -m scripts.run webhook --port $PORT; exec bash"

sleep 2

echo "Starting ngrok in new Git Bash window..."
start "" "C:/Program Files/Git/bin/bash.exe" -c "cd '$PROJECT_ROOT'; ngrok http $PORT; exec bash"

echo ""
echo "🚀 Webhook + ngrok launched in separate Git Bash terminals!"