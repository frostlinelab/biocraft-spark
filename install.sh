#!/usr/bin/env bash
set -euo pipefail

# ── Biocraft-Spark installer & launcher ──────────────────────────────────────
#
# Usage:
#   ./install.sh                Pull pre-built image and start (default)
#   ./install.sh --build        Build from source and start
#   ./install.sh --dev          Start in dev mode (live backend reload, foreground)
#   ./install.sh start          Start the server
#   ./install.sh stop           Stop the server
#   ./install.sh restart        Restart the server
#   ./install.sh logs           Tail server logs (Ctrl+C to exit)
#   ./install.sh status         Show container status
#   ./install.sh --help         Show this help message

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Config ───────────────────────────────────────────────────────────────────
PORT=25568
DATA_DIRS=("uploads" "plugins" "run_outputs")
COMPOSE_CMD=""

# ── Preflight checks ─────────────────────────────────────────────────────────

check_docker() {
    if ! command -v docker &>/dev/null; then
        error "Docker is not installed or not in PATH."
        echo "  Install Docker:  https://docs.docker.com/get-docker/"
        echo "  Or OrbStack:     https://orbstack.dev/"
        exit 1
    fi
    if ! docker info &>/dev/null; then
        error "Docker daemon is not running."
        echo "  Start Docker Desktop or OrbStack, then re-run this script."
        exit 1
    fi
    ok "Docker is running."
}

check_compose() {
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        error "Docker Compose is not installed."
        echo "  Docker Compose v2 is bundled with Docker Desktop."
        echo "  Install: https://docs.docker.com/compose/install/"
        exit 1
    fi
    ok "Docker Compose is available."
}

check_socket() {
    local sockets=(
        "/var/run/docker.sock"
        "$HOME/.orbstack/run/docker.sock"
        "$HOME/.docker/run/docker.sock"
    )
    for sock in "${sockets[@]}"; do
        if [ -S "$sock" ]; then
            ok "Docker socket: $sock"
            if [ "$sock" != "/var/run/docker.sock" ]; then
                warn "Non-standard socket path. If compose fails to connect,"
                warn "update the socket path in docker-compose.yml."
            fi
            return 0
        fi
    done
    warn "No Docker socket found at standard paths."
    warn "Docker-out-of-Docker may not work. Continuing anyway..."
}

# ── Data directories ─────────────────────────────────────────────────────────

ensure_data_dirs() {
    info "Preparing data directories..."
    for dir in "${DATA_DIRS[@]}"; do
        mkdir -p "$dir"
    done
    # db.sqlite3 must be a FILE — Docker creates a directory if the source
    # path doesn't exist, which breaks Django. Fix if that happened.
    if [ -d "db.sqlite3" ]; then
        warn "db.sqlite3 is a directory (likely auto-created by Docker). Removing..."
        rm -rf "db.sqlite3"
    fi
    touch "db.sqlite3"
    ok "Data directories ready."
}

# ── Compose wrappers ─────────────────────────────────────────────────────────

compose_up() {
    local mode="${1:-pull}"
    case "$mode" in
        pull)
            info "Pulling pre-built image from GHCR..."
            $COMPOSE_CMD pull
            info "Starting Biocraft-Spark..."
            $COMPOSE_CMD up -d
            ;;
        build)
            info "Building from source (multi-stage build, may take a few minutes)..."
            $COMPOSE_CMD build --no-cache
            info "Starting Biocraft-Spark..."
            $COMPOSE_CMD up -d
            ;;
        dev)
            info "Starting in dev mode (live backend reload, foreground)..."
            info "For frontend hot-reload, run in another terminal:"
            info "  cd frontend && npm install && npm run dev"
            echo ""
            $COMPOSE_CMD -f docker-compose.yml -f docker-compose.dev.yml up
            ;;
    esac
}

wait_for_server() {
    info "Waiting for server (port $PORT)..."
    local max_wait=60
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
            ok "Server is ready!"
            echo ""
            echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║  Biocraft-Spark is running!                    ║${NC}"
            echo -e "${GREEN}║                                                ║${NC}"
            echo -e "${GREEN}║  Open:  http://127.0.0.1:${PORT}/              ║${NC}"
            echo -e "${GREEN}║                                                ║${NC}"
            echo -e "${GREEN}║  Stop:  ./install.sh stop                      ║${NC}"
            echo -e "${GREEN}║  Logs:  ./install.sh logs                      ║${NC}"
            echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    warn "Server didn't respond within ${max_wait}s."
    warn "Check logs: ./install.sh logs"
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_install() {
    local mode="${1:-pull}"
    check_docker
    check_compose
    check_socket
    ensure_data_dirs
    compose_up "$mode"
    if [ "$mode" != "dev" ]; then
        wait_for_server
    fi
}

cmd_start() {
    check_docker
    check_compose
    ensure_data_dirs
    $COMPOSE_CMD up -d
    wait_for_server
}

cmd_stop() {
    check_compose
    $COMPOSE_CMD down
    ok "Biocraft-Spark stopped."
}

cmd_restart() {
    check_compose
    $COMPOSE_CMD restart
    ok "Biocraft-Spark restarted."
    wait_for_server
}

cmd_logs() {
    $COMPOSE_CMD logs -f --tail=100
}

cmd_status() {
    $COMPOSE_CMD ps
}

show_help() {
    cat <<'EOF'
Biocraft-Spark installer & launcher

Usage:
  ./install.sh                Pull pre-built image and start (default)
  ./install.sh --build        Build from source and start
  ./install.sh --dev          Start in dev mode (live backend reload)
  ./install.sh start          Start the server
  ./install.sh stop           Stop the server
  ./install.sh restart        Restart the server
  ./install.sh logs           Tail server logs (Ctrl+C to exit)
  ./install.sh status         Show container status
  ./install.sh --help         Show this help message

Options:
  --build     Build the Docker image from source instead of pulling
  --dev       Run in development mode with live backend reload
  -h, --help  Show this help message

Prerequisites:
  - Docker (Desktop, Engine, or OrbStack) running on the host
  - No Node.js or Python required (image is self-contained)

  --build:  No host Node.js/Python needed (multi-stage Dockerfile builds
            the frontend inside Docker).
  --dev:    Requires Node.js 20+ on the host for frontend hot-reload.
EOF
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
    case "${1:-install}" in
        install|"")
            cmd_install "pull"
            ;;
        --build)
            cmd_install "build"
            ;;
        --dev)
            cmd_install "dev"
            ;;
        start)   cmd_start   ;;
        stop)    cmd_stop    ;;
        restart) cmd_restart ;;
        logs)    cmd_logs    ;;
        status)  cmd_status  ;;
        -h|--help) show_help ;;
        *)
            error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
