#!/usr/bin/env bash
source "${ROS_SETUP_FILE:-$HOME/ros2_ws/install/setup.bash}"

ROS_TCP_PORT=10000
LOCK_FILE="${TMPDIR:-/tmp}/visionmapscanner_ros_tcp_endpoint_${ROS_TCP_PORT}.lock"

port_listener() {
    if ! command -v ss >/dev/null 2>&1; then
        if command -v lsof >/dev/null 2>&1; then
            lsof -nP -iTCP:"${ROS_TCP_PORT}" -sTCP:LISTEN 2>/dev/null
            return $?
        fi
        echo "Neither ss nor lsof is available to check ROS TCP port ${ROS_TCP_PORT}" >&2
        return 2
    fi
    local output
    output="$(ss -H -ltnp "sport = :${ROS_TCP_PORT}" 2>/dev/null)" || return 2
    printf '%s' "${output}"
}

existing_listener="$(port_listener)"
if [[ $? -eq 2 ]]; then
    exit 98
fi
if [[ -n "${existing_listener}" ]]; then
    if pgrep -af 'ros_tcp_endpoint' >/dev/null 2>&1; then
        echo "ROS_TCP_ENDPOINT_REUSED port=${ROS_TCP_PORT}"
        exit 0
    fi
    echo "ROS_TCP_PORT_CONFLICT port=${ROS_TCP_PORT}; refusing to stop the existing process" >&2
    exit 98
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    for attempt in {1..30}; do
        existing_listener="$(port_listener)"
        if [[ $? -eq 2 ]]; then
            exit 98
        fi
        if [[ -n "${existing_listener}" ]] && pgrep -af 'ros_tcp_endpoint' >/dev/null 2>&1; then
            echo "ROS_TCP_ENDPOINT_REUSED port=${ROS_TCP_PORT}"
            exit 0
        fi
        sleep 0.1
    done
    echo "ROS_TCP_ENDPOINT_LAUNCH_IN_PROGRESS port=${ROS_TCP_PORT}" >&2
    exit 98
fi

# Recheck after acquiring the launcher lock to close the simultaneous-start race.
existing_listener="$(port_listener)"
if [[ $? -eq 2 ]]; then
    exit 98
fi
if [[ -n "${existing_listener}" ]]; then
    if pgrep -af 'ros_tcp_endpoint' >/dev/null 2>&1; then
        echo "ROS_TCP_ENDPOINT_REUSED port=${ROS_TCP_PORT}"
        exit 0
    fi
    echo "ROS_TCP_PORT_CONFLICT port=${ROS_TCP_PORT}; refusing to stop the existing process" >&2
    exit 98
fi

exec ros2 run ros_tcp_endpoint default_server_endpoint --ros-args \
    -p ROS_IP:=127.0.0.1 -p ROS_TCP_PORT:=${ROS_TCP_PORT}

