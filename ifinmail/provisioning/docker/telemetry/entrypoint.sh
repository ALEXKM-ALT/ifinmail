#!/usr/bin/env sh
set -eu

LOG_FILE="${TELEMETRY_LOG_FILE:-/logs/telemetry.log}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-docker}"
EXCLUDE_SERVICE="${TELEMETRY_SERVICE_NAME:-telemetry}"
POLL_INTERVAL="${TELEMETRY_POLL_INTERVAL:-10}"
MAX_LOG_SIZE="${TELEMETRY_MAX_LOG_SIZE:-52428800}"  # 50 MB default
FINGERPRINT_INTERVAL="${TELEMETRY_FINGERPRINT_INTERVAL:-30}"
STATE_DIR="/tmp/ifinmail-telemetry"

mkdir -p "$(dirname "$LOG_FILE")" "$STATE_DIR"
touch "$LOG_FILE"

write_line() {
    printf '%s telemetry %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" >> "$LOG_FILE"
}

rotate_log() {
    # Rotate when log exceeds max size (copy + truncate — safe for secondary log aggregation)
    if [ -f "$LOG_FILE" ]; then
        size="$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)"
        if [ "${size:-0}" -gt "$MAX_LOG_SIZE" ]; then
            write_line "rotating log (${size} bytes exceeds ${MAX_LOG_SIZE})"
            cp "$LOG_FILE" "${LOG_FILE}.1" 2>/dev/null || true
            : > "$LOG_FILE"
            write_line "log rotated, previous data in ${LOG_FILE}.1"
        fi
    fi
}

emit_fingerprint() {
    # Snapshot all running containers with their image tags for traceability.
    # fingerprint lines let you correlate log entries with specific image versions
    # and detect container restarts, version changes, etc.
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    printf '%s fingerprint type=host host="%s" kernel="%s" project="%s"\n' \
        "$ts" "$(hostname 2>/dev/null || echo 'unknown')" "$(uname -r 2>/dev/null || echo 'unknown')" \
        "$PROJECT_NAME" >> "$LOG_FILE"

    docker ps \
        --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
        --format '{{.ID}}|{{.Label "com.docker.compose.service"}}|{{.Names}}|{{.Image}}' \
        | while IFS='|' read -r cid svc name image; do
            [ -n "$cid" ] || continue
            [ "$svc" != "$EXCLUDE_SERVICE" ] || continue
            short_id="$(echo "$cid" | cut -c1-12)"
            printf '%s fingerprint type=container container="%s" service="%s" image="%s" id="%s"\n' \
                "$ts" "$name" "$svc" "$image" "$short_id" >> "$LOG_FILE"
        done
}

write_line "collector starting for compose project '${PROJECT_NAME}'"

# Emit initial fingerprint at startup
emit_fingerprint

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

        # Emit container fingerprint on first connect for traceability
        ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        image_info="$(docker inspect --format '{{.Config.Image}}|{{.Created}}|{{.State.Status}}|{{.RestartCount}}' "$container_id" 2>/dev/null || echo 'unknown|unknown|unknown|0')"
        printf '%s fingerprint type=container-start container="%s" service="%s" image="%s" created="%s" status="%s" restarts="%s" id="%s"\n' \
            "$ts" "$container_name" "$service" \
            "$(echo "$image_info" | cut -d'|' -f1)" \
            "$(echo "$image_info" | cut -d'|' -f2)" \
            "$(echo "$image_info" | cut -d'|' -f3)" \
            "$(echo "$image_info" | cut -d'|' -f4)" \
            "$(echo "$container_id" | cut -c1-12)" >> "$LOG_FILE"
    fi

    (
        docker logs --timestamps --tail "$tail_lines" -f "$container_id" 2>&1 \
            | awk -v service="$service" -v container="$container_name" '
                # Dedup: collapse repeated identical lines into a single entry with dedup=N.
                # Fingerprint = line content minus the docker --timestamps prefix.
                # Applies to both HTTP error lines (4xx/5xx) and non-HTTP log lines.
                function fp(line) {
                    sub(/^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9](.[0-9]+)?Z /, "", line);
                    return line;
                }
                {
                    suffix = " service=" service " container=" container;
                    raw = $0;

                    # Filter: keep 4xx/5xx HTTP responses or non-HTTP (non-3-digit) log lines.
                    # Drop 2xx/3xx HTTP responses (noisy health checks, static files).
                    if ($9 ~ /^[45][0-9][0-9]$/ || $9 !~ /^[0-9][0-9][0-9]$/) {
                        f = fp(raw);

                        if (f == last_fp && f != "") {
                            dedup_count++;
                            next;
                        }

                        # Flush previous dedup batch
                        if (last_fp != "") {
                            if (dedup_count > 0) {
                                printf "%s%s dedup=%d\n", last_content, last_suffix, dedup_count + 1;
                            } else {
                                printf "%s%s\n", last_content, last_suffix;
                            }
                        }

                        last_content = raw;
                        last_fp = f;
                        last_suffix = suffix;
                        dedup_count = 0;
                    } else {
                        # 2xx/3xx HTTP -- flush pending dedup, skip current
                        if (last_fp != "") {
                            if (dedup_count > 0) {
                                printf "%s%s dedup=%d\n", last_content, last_suffix, dedup_count + 1;
                            } else {
                                printf "%s%s\n", last_content, last_suffix;
                            }
                        }
                        last_fp = "";
                        dedup_count = 0;
                    }
                    fflush();
                }
                END {
                    # Flush remaining dedup on pipeline close (container stops / docker logs exits)
                    if (last_fp != "") {
                        if (dedup_count > 0) {
                            printf "%s%s dedup=%d\n", last_content, last_suffix, dedup_count + 1;
                        } else {
                            printf "%s%s\n", last_content, last_suffix;
                        }
                        fflush();
                    }
                }
            ' >> "$LOG_FILE"
    ) &
    echo "$!" > "$pid_file"
    write_line "watching service=${service} container=${container_name} id=${container_id}"
}

fingerprint_counter=0

while :; do
    rotate_log
    docker ps \
        --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
        --format '{{.ID}} {{.Label "com.docker.compose.service"}} {{.Names}}' \
        | while read -r container_id service container_name; do
            [ -n "${container_id:-}" ] || continue
            [ "$service" != "$EXCLUDE_SERVICE" ] || continue
            start_log_stream "$container_id" "$service" "$container_name"
        done

    # Periodic fingerprint refresh to track version changes and container restarts
    fingerprint_counter=$((fingerprint_counter + 1))
    if [ "$fingerprint_counter" -ge "$FINGERPRINT_INTERVAL" ]; then
        fingerprint_counter=0
        emit_fingerprint
    fi

    sleep "$POLL_INTERVAL"
done
