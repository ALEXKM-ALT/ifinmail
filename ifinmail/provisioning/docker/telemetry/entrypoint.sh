#!/usr/bin/env sh
set -eu

LOG_FILE="${TELEMETRY_LOG_FILE:-/logs/telemetry.log}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-docker}"
EXCLUDE_SERVICE="${TELEMETRY_SERVICE_NAME:-telemetry}"
POLL_INTERVAL="${TELEMETRY_POLL_INTERVAL:-10}"
STATE_DIR="/tmp/ifinmail-telemetry"

mkdir -p "$(dirname "$LOG_FILE")" "$STATE_DIR"
touch "$LOG_FILE"

write_line() {
    printf '%s telemetry %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" >> "$LOG_FILE"
}

write_line "collector starting for compose project '${PROJECT_NAME}'"

start_log_stream() {
    container_id="$1"
    service="$2"
    container_name="$3"
    pid_file="${STATE_DIR}/${container_id}.pid"
    seen_file="${STATE_DIR}/${container_id}.seen"

    # Clean up stale PID files
    for pf in "$STATE_DIR"/*.pid; do
        [ -f "$pf" ] || continue
        cid=$(basename "$pf" .pid)
        # Remove PID files for non-running processes
        if ! kill -0 "$(cat "$pf")" 2>/dev/null; then
            rm -f "$pf" "${STATE_DIR}/${cid}.seen" 2>/dev/null || true
        fi
    done

    if [ -s "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        return 0
    fi

    # Determine tail length: full tail on first connect, 0 on reconnect
    if [ -f "$seen_file" ]; then
        tail_lines=0
    else
        tail_lines="${TELEMETRY_TAIL_LINES:-100}"
        touch "$seen_file"
    fi

    (
        docker logs --timestamps --tail "$tail_lines" -f "$container_id" 2>&1 \
            | awk -v service="$service" -v container="$container_name" '
                {
                    print $0 " service=" service " container=" container;
                    fflush();
                }
            ' >> "$LOG_FILE"
    ) &
    echo "$!" > "$pid_file"
    write_line "watching service=${service} container=${container_name} id=${container_id}"
}

while :; do
    docker ps \
        --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
        --format '{{.ID}} {{.Label "com.docker.compose.service"}} {{.Names}}' \
        | while read -r container_id service container_name; do
            [ -n "${container_id:-}" ] || continue
            [ "$service" != "$EXCLUDE_SERVICE" ] || continue
            start_log_stream "$container_id" "$service" "$container_name"
        done

    sleep "$POLL_INTERVAL"
done
