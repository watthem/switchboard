#!/usr/bin/env bash
# claude-code-hook.sh — Report Claude Code tool events to Switchboard
#
# Configure as a Claude Code hook in .claude/settings.local.json:
#   {
#     "hooks": {
#       "PreToolUse":  [{ "type": "command", "command": "/path/to/claude-code-hook.sh" }],
#       "PostToolUse": [{ "type": "command", "command": "/path/to/claude-code-hook.sh" }],
#       "Stop":        [{ "type": "command", "command": "/path/to/claude-code-hook.sh" }]
#     }
#   }
#
# Environment variables:
#   SWITCHBOARD_URL      — Switchboard endpoint (default: http://localhost:59237)
#   SWITCHBOARD_AGENT_ID — Agent identifier (default: claude-code)
#   SWITCHBOARD_CC_TOKEN — Bearer token (or reads from SWITCHBOARD_TOKEN_FILE)
#   SWITCHBOARD_TOKEN_FILE — Path to token file (default: .switchboard-token in script dir)
set -euo pipefail

SWITCHBOARD_URL="${SWITCHBOARD_URL:-http://localhost:59237}"
AGENT_ID="${SWITCHBOARD_AGENT_ID:-claude-code}"
TOKEN_FILE="${SWITCHBOARD_TOKEN_FILE:-$(dirname "$0")/.switchboard-token}"

if [ -n "${SWITCHBOARD_CC_TOKEN:-}" ]; then
  TOKEN="$SWITCHBOARD_CC_TOKEN"
elif [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(cat "$TOKEN_FILE")
else
  exit 0
fi

INPUT=$(cat)
EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty' 2>/dev/null)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$EVENT" in
  PreToolUse)
    case "$TOOL" in
      Bash)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.command // "-"' 2>/dev/null | head -c 120) ;;
      Read|Write|Edit)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // "-"' 2>/dev/null) ;;
      Grep)
        P=$(echo "$INPUT" | jq -r '.tool_input.pattern // ""' 2>/dev/null)
        D=$(echo "$INPUT" | jq -r '.tool_input.path // "."' 2>/dev/null)
        TARGET="grep:${P:0:40} in ${D}" ;;
      Glob)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.pattern // "-"' 2>/dev/null) ;;
      WebSearch)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.query // "-"' 2>/dev/null | head -c 80) ;;
      Task|TaskCreate|TaskUpdate)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input.description // .tool_input.subject // .tool_input.taskId // "-"' 2>/dev/null | head -c 80) ;;
      *)
        TARGET=$(echo "$INPUT" | jq -r '.tool_input | keys[0] // "-"' 2>/dev/null) ;;
    esac
    ACTION="$TOOL"
    RESULT="pending"
    DETAIL="session:${SESSION:0:12} cwd:${CWD}"
    ;;
  PostToolUse)
    ACTION="$TOOL"
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // .tool_input.pattern // "-"' 2>/dev/null | head -c 120)
    RESULT="success"
    DETAIL="session:${SESSION:0:12}"
    ;;
  PostToolUseFailure)
    ACTION="$TOOL"
    TARGET=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.command // .tool_input.pattern // "-"' 2>/dev/null | head -c 120)
    RESULT="failure"
    DETAIL="session:${SESSION:0:12}"
    ;;
  Stop)
    ACTION="turn_complete"
    TARGET="session:${SESSION:0:12}"
    RESULT="success"
    DETAIL="cwd:${CWD}"
    ;;
  SessionStart)
    ACTION="session_start"
    TARGET="$AGENT_ID"
    RESULT="success"
    DETAIL="cwd:${CWD}"
    # Send initial telemetry
    RTT_MS=$(curl -s -o /dev/null -w "%{time_total}" "${SWITCHBOARD_URL}/health" 2>/dev/null | awk '{printf "%.1f", $1 * 1000}')
    curl -s -X POST "${SWITCHBOARD_URL}/api/v1/telemetry" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${TOKEN}" \
      -d "{\"agent_id\":\"${AGENT_ID}\",\"timestamp\":\"${TIMESTAMP}\",\"probe_source\":\"hook\",\"telemetry_mode\":\"sidecar_only\",\"network_rtt_ms\":${RTT_MS:-0},\"network_jitter_ms\":0.0,\"is_remote_session\":false}" > /dev/null 2>&1 &
    ;;
  SessionEnd)
    ACTION="session_end"
    TARGET="$AGENT_ID"
    RESULT="success"
    DETAIL="session:${SESSION:0:12}"
    ;;
  *)
    exit 0 ;;
esac

curl -s -X POST "${SWITCHBOARD_URL}/api/v1/events" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"agent_id\":\"${AGENT_ID}\",\"timestamp\":\"${TIMESTAMP}\",\"action\":\"${ACTION}\",\"target\":$(echo "$TARGET" | jq -Rs .),\"result\":\"${RESULT}\",\"detail\":$(echo "$DETAIL" | jq -Rs .)}" > /dev/null 2>&1 &

exit 0
