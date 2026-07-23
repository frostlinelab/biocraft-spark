#!/usr/bin/env bash
set -euo pipefail

# ── Biocraft-Spark installer & launcher ──────────────────────────────────────
#
# One-line install (no git, no Docker, no Xcode/CLT required):
#
#   curl -fsSL https://raw.githubusercontent.com/frostlinelab/biocraft-spark/main/install.sh | bash
#
# What it does:
#   1. Ensures a container runtime is available:
#        - Linux : installs Docker Engine via get.docker.com (if missing)
#        - macOS : installs OrbStack via Homebrew or direct .dmg (if missing),
#                  launches it, and best-effort enables "start at login"
#   2. Fetches only docker-compose.standalone.yml — NOT the whole repo — so
#      users without git/Xcode can install.
#   3. Pulls the pre-built multi-arch image from GHCR and starts the server.
#   4. The container entrypoint runs DB migrations automatically on startup,
#      so /api/dashboard-stats/ and /api/marketplace/catalog/ work out of the
#      box (a manual `migrate` is no longer needed).
#
# Usage:
#   ./install.sh                Install / start (pull pre-built image)
#   ./install.sh --build        Build from source (requires the full repo)
#   ./install.sh --dev          Dev mode (requires the full repo + Node.js 20+)
#   ./install.sh start          Start the server
#   ./install.sh stop           Stop the server
#   ./install.sh restart        Restart the server
#   ./install.sh logs           Tail server logs (Ctrl+C to exit)
#   ./install.sh status         Show container status
#   ./install.sh --dir <path>   Install into <path> (default: ~/.biocraft-spark)
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
REPO_RAW_BASE="https://raw.githubusercontent.com/frostlinelab/biocraft-spark/main"
DATA_DIRS=("uploads" "plugins" "run_outputs")

# Resolved at runtime
INSTALL_DIR="${BIOCRAFT_INSTALL_DIR:-}"
COMPOSE_DIR=""
COMPOSE_FILE_NAME=""
REPO_MODE=false
COMPOSE_CMD=""
DOCKER_SOCK=""
DOCKER_PREFIX=""

# ── OS detection ─────────────────────────────────────────────────────────────

detect_os() {
    case "$(uname -s)" in
        Darwin) OS="macos" ;;
        Linux)  OS="linux" ;;
        *)      OS="other" ;;
    esac
}

# ── Container runtime provisioning ───────────────────────────────────────────

have_docker_cli() { command -v docker >/dev/null 2>&1; }

docker_daemon_ok() {
    # Try without sudo first, then passwordless sudo.
    if docker info >/dev/null 2>&1; then
        return 0
    fi
    if [ "$(id -u)" -ne 0 ] && sudo -n true >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

_resolve_prefix() {
    # Decide whether docker commands need sudo in the current shell.
    if [ "$(id -u)" -eq 0 ]; then
        DOCKER_PREFIX=""
        return
    fi
    if docker info >/dev/null 2>&1; then
        DOCKER_PREFIX=""
        return
    fi
    if sudo -n true >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
        DOCKER_PREFIX="sudo"
        warn "Docker needs sudo in this session. Log out/in or run 'newgrp docker' to drop sudo."
        return
    fi
    DOCKER_PREFIX=""
}

_start_daemon() {
    # Daemon installed but not running — try to start it.
    case "$OS" in
        macos)
            if [ -d /Applications/OrbStack.app ]; then
                open -a OrbStack
            elif [ -d /Applications/Docker.app ]; then
                open -a Docker
            fi
            ;;
        linux)
            sudo systemctl start docker 2>/dev/null || sudo service docker start 2>/dev/null || true
            ;;
    esac
}

install_docker_linux() {
    info "No Docker detected. Installing Docker Engine via get.docker.com..."
    if ! command -v curl >/dev/null 2>&1; then
        error "curl is required to install Docker. Install it (e.g. 'sudo apt-get install -y curl') and re-run."
        exit 1
    fi
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    sudo systemctl enable --now docker 2>/dev/null || sudo service docker start 2>/dev/null || true
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    rm -f /tmp/get-docker.sh
    echo ""
    ok "Docker Engine installed and started."
    warn "Your user has been added to the 'docker' group."
    warn "This session uses sudo for Docker — log out/in (or run 'newgrp docker') to drop sudo later."
    DOCKER_PREFIX="sudo"
}

# Resolve the latest OrbStack .dmg URL for the given arch from the Homebrew cask
# API (works without brew/CLT/git; only needs curl).
orbstack_cask_url() {
    local orb_arch="$1" json
    json="$(curl -fsSL https://formulae.brew.sh/api/cask/orbstack.json)" || return 1
    printf '%s' "$json" \
        | grep -o "\"url\":\"https://cdn-updates.orbstack.dev/${orb_arch}/[^\"]*\"" \
        | head -1 \
        | sed 's/"url":"//;s/"$//'
}

install_orbstack_dmg() {
    info "Homebrew not found. Downloading OrbStack directly (no Xcode/CLT needed)..."
    local arch orb_arch url dmg mp
    arch="$(uname -m)"
    case "$arch" in
        arm64)  orb_arch="arm64" ;;
        x86_64) orb_arch="amd64" ;;
        *) error "Unsupported Mac architecture: $arch"; exit 1 ;;
    esac
    url="$(orbstack_cask_url "$orb_arch")" || {
        error "Could not resolve the OrbStack download URL."
        echo "  Install manually from https://orbstack.dev/download, then re-run this script."
        exit 1
    }
    dmg="$(mktemp -u -t orbstack).dmg"
    info "Downloading $url"
    curl -fSL -o "$dmg" "$url"
    mp="$(mktemp -d -t orbstack)"
    hdiutil attach "$dmg" -nobrowse -readonly -mountpoint "$mp" >/dev/null
    if [ ! -d "$mp/OrbStack.app" ]; then
        hdiutil detach "$mp" >/dev/null 2>&1 || true
        error "OrbStack.app not found inside the downloaded disk image."
        exit 1
    fi
    if cp -R "$mp/OrbStack.app" /Applications/ 2>/dev/null; then :; else
        sudo cp -R "$mp/OrbStack.app" /Applications/
    fi
    hdiutil detach "$mp" >/dev/null 2>&1 || true
    rm -rf "$mp" "$dmg"
    ok "OrbStack installed to /Applications."
}

launch_and_wait_orbstack() {
    if ! pgrep -f "OrbStack.app/Contents/MacOS" >/dev/null 2>&1; then
        info "Launching OrbStack (approve the first-launch permission prompts)..."
        open -a OrbStack
    fi

    info "Waiting for the OrbStack Docker engine to come online..."
    info "First launch can take a few minutes on slower Macs — this keeps checking"
    info "until OrbStack is ready. Press Ctrl+C to abort."

    local poll=5          # readiness check interval — fast detection, near-zero cost
    local beat=15         # progress heartbeat interval (user-facing feedback cadence)
    local elapsed=0
    local since_beat=0
    local seen_running=0

    # No fixed timeout: we wait until ready (slow machines included). Two safety
    # nets prevent an infinite hang: (1) if OrbStack was running but stops
    # (crash / user quit), bail; (2) if it never appears within 60s, bail.
    while true; do
        hash -r 2>/dev/null || true
        if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
            ok "OrbStack is ready (waited ${elapsed}s)."
            return 0
        fi

        if pgrep -f "OrbStack.app/Contents/MacOS" >/dev/null 2>&1; then
            seen_running=1
        elif [ "$seen_running" -eq 1 ]; then
            error "OrbStack stopped running. Reopen it (check for errors), then re-run this script."
            exit 1
        elif [ "$elapsed" -ge 60 ]; then
            error "OrbStack did not start. Open /Applications/OrbStack.app manually, then re-run."
            exit 1
        fi

        sleep "$poll"
        elapsed=$((elapsed + poll))
        since_beat=$((since_beat + poll))
        if [ "$since_beat" -ge "$beat" ]; then
            since_beat=0
            warn "Still waiting for OrbStack... ${elapsed}s elapsed. That's normal on a slow Mac — approve any permission prompts in the OrbStack window."
        fi
    done
}

enable_orbstack_autostart() {
    # Best-effort login item. macOS may prompt for Automation permission; if it
    # fails, the troubleshooting guide documents the manual toggle.
    if osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/OrbStack.app", hidden:false}' >/dev/null 2>&1; then
        ok "OrbStack added to login items (starts on boot)."
    else
        warn "Could not auto-enable the login item."
        warn "Open OrbStack → Settings → enable 'Start OrbStack at login'."
    fi
}

install_orbstack() {
    if [ -d /Applications/OrbStack.app ]; then
        ok "OrbStack is already installed."
    elif command -v brew >/dev/null 2>&1; then
        info "Installing OrbStack via Homebrew..."
        brew install --cask orbstack
    else
        install_orbstack_dmg
    fi
    launch_and_wait_orbstack
    enable_orbstack_autostart
    DOCKER_PREFIX=""
}

ensure_runtime() {
    detect_os

    # Already have a working daemon? Use it (don't reinstall over Docker Desktop).
    if have_docker_cli; then
        if docker info >/dev/null 2>&1; then
            DOCKER_PREFIX=""
            ok "Docker is running."
            return 0
        fi
        if [ "$(id -u)" -ne 0 ] && sudo -n true >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
            DOCKER_PREFIX="sudo"
            ok "Docker is running (via sudo)."
            warn "Log out/in or run 'newgrp docker' to drop sudo."
            return 0
        fi
        # CLI present but daemon down — try to start it, then re-check.
        _start_daemon || true
        if docker info >/dev/null 2>&1; then
            DOCKER_PREFIX=""
            ok "Docker is running."
            return 0
        fi
    fi

    # No working runtime — install the platform default.
    case "$OS" in
        macos) install_orbstack ;;
        linux) install_docker_linux ;;
        *)
            error "Unsupported OS for automatic Docker install ($(uname -s))."
            echo "  Install Docker manually: https://docs.docker.com/get-docker/"
            echo "  Then re-run this script."
            exit 1
            ;;
    esac
    ok "Container runtime is ready."
}

ensure_compose_cmd() {
    if $DOCKER_PREFIX docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        error "Docker Compose is not installed."
        echo "  Docker Compose v2 ships with Docker Engine (Linux) and OrbStack (macOS)."
        echo "  Install: https://docs.docker.com/compose/install/"
        exit 1
    fi
    ok "Docker Compose is available ($COMPOSE_CMD)."
}

# Detect the host Docker socket path (Linux / Docker Desktop / OrbStack).
detect_socket() {
    local sock
    for sock in /var/run/docker.sock "$HOME/.orbstack/run/docker.sock" "$HOME/.docker/run/docker.sock"; do
        if [ -S "$sock" ]; then
            DOCKER_SOCK="$sock"
            return 0
        fi
    done
    return 1
}

# ── Install dir / mode resolution ────────────────────────────────────────────

resolve_mode() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || script_dir="$PWD"

    if [ -z "$INSTALL_DIR" ]; then
        # Running from a full repo checkout (has docker-compose.yml + manage.py)?
        if [ -f "$script_dir/docker-compose.yml" ] && [ -f "$script_dir/manage.py" ]; then
            INSTALL_DIR="$script_dir"
        else
            INSTALL_DIR="$HOME/.biocraft-spark"
        fi
    fi

    if [ -f "$INSTALL_DIR/docker-compose.yml" ] && [ -f "$INSTALL_DIR/manage.py" ]; then
        REPO_MODE=true
        COMPOSE_FILE_NAME="docker-compose.yml"
    else
        REPO_MODE=false
        COMPOSE_FILE_NAME="docker-compose.standalone.yml"
    fi
    COMPOSE_DIR="$INSTALL_DIR"
}

# Fetch the standalone compose profile (curl install path only).
fetch_standalone_compose() {
    [ "$REPO_MODE" = "true" ] && return 0
    mkdir -p "$COMPOSE_DIR"
    if [ ! -f "$COMPOSE_DIR/$COMPOSE_FILE_NAME" ]; then
        info "Fetching compose profile (no repo clone needed)..."
        curl -fsSL "$REPO_RAW_BASE/$COMPOSE_FILE_NAME" -o "$COMPOSE_DIR/$COMPOSE_FILE_NAME"
    fi
}

# Persist install.sh into the install dir so curl-installed users can manage
# the server afterwards (./install.sh stop | restart | logs | status).
save_self() {
    [ "$REPO_MODE" = "true" ] && return 0
    local self="${BASH_SOURCE[0]:-}"
    if { [ -z "$self" ] || [ ! -f "$self" ]; } && [ ! -f "$COMPOSE_DIR/install.sh" ]; then
        curl -fsSL "$REPO_RAW_BASE/install.sh" -o "$COMPOSE_DIR/install.sh" 2>/dev/null || true
        chmod +x "$COMPOSE_DIR/install.sh" 2>/dev/null || true
    fi
}

ensure_data_dirs() {
    info "Preparing data directories in $COMPOSE_DIR ..."
    mkdir -p "$COMPOSE_DIR"
    for dir in "${DATA_DIRS[@]}"; do
        mkdir -p "$COMPOSE_DIR/$dir"
    done
    # db.sqlite3 must be a FILE — Docker creates a directory if the source
    # path doesn't exist, which breaks Django. Fix if that happened.
    if [ -d "$COMPOSE_DIR/db.sqlite3" ]; then
        warn "db.sqlite3 is a directory (likely auto-created by Docker). Removing..."
        rm -rf "$COMPOSE_DIR/db.sqlite3"
    fi
    [ -f "$COMPOSE_DIR/db.sqlite3" ] || touch "$COMPOSE_DIR/db.sqlite3"
    ok "Data directories ready."
}

# ── Server lifecycle ─────────────────────────────────────────────────────────

wait_for_server() {
    info "Waiting for server (port $PORT)..."
    local max_wait=90
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
            ok "Server is ready!"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done
    warn "Server didn't respond within ${max_wait}s."
    warn "Check logs: ./install.sh logs"
}

# Beta2's image runs migrations in its entrypoint. For older images (or if the
# entrypoint was bypassed), verify a DB-backed endpoint and self-heal.
ensure_migrated() {
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/dashboard-stats/" 2>/dev/null || echo 000)"
    if [ "$code" = "200" ]; then
        return 0
    fi
    warn "Dashboard API returned HTTP $code — running migrations explicitly..."
    if ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" exec -T web python manage.py migrate --noinput ) >/dev/null 2>&1; then
        ok "Migrations applied."
    else
        warn "Automatic migrate failed. Run manually:"
        echo "  cd \"$COMPOSE_DIR\" && $DOCKER_PREFIX $COMPOSE_CMD -f $COMPOSE_FILE_NAME exec web python manage.py migrate"
        return 0
    fi
    if [ "$code" = "000" ] || [ "$code" = "500" ]; then
        ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" restart ) >/dev/null 2>&1 || true
        wait_for_server
    fi
}

print_success() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Biocraft-Spark is running!                    ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║  Open:  http://127.0.0.1:${PORT}/              ║${NC}"
    echo -e "${GREEN}║                                                ║${NC}"
    echo -e "${GREEN}║  Stop:  ./install.sh stop                      ║${NC}"
    echo -e "${GREEN}║  Logs:  ./install.sh logs                      ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
    local ip
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [ -n "$ip" ]; then
        echo -e "  ${BLUE}LAN access:${NC} http://${ip}:${PORT}/"
    fi
    if [ "$REPO_MODE" = "false" ]; then
        echo -e "  ${BLUE}Install dir:${NC} ${COMPOSE_DIR}"
        echo -e "  ${BLUE}Manage:${NC} cd \"${COMPOSE_DIR}\" && ./install.sh {stop|restart|logs|status}"
    fi
}

# ── Commands ─────────────────────────────────────────────────────────────────

setup_common() {
    _resolve_prefix
    ensure_compose_cmd
}

cmd_install() {
    local mode="${1:-pull}"
    if { [ "$mode" = "build" ] || [ "$mode" = "dev" ]; } && [ "$REPO_MODE" != "true" ]; then
        error "--build/--dev require the full repository checkout. Clone first:"
        echo "  git clone https://github.com/frostlinelab/biocraft-spark.git"
        exit 1
    fi

    ensure_runtime
    ensure_compose_cmd
    detect_socket || DOCKER_SOCK="/var/run/docker.sock"
    export DOCKER_SOCK
    fetch_standalone_compose
    ensure_data_dirs

    case "$mode" in
        pull)
            info "Pulling pre-built image from GHCR..."
            ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" pull )
            info "Starting Biocraft-Spark..."
            ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" up -d )
            ;;
        build)
            info "Building from source (multi-stage build, may take a few minutes)..."
            ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" build --no-cache )
            info "Starting Biocraft-Spark..."
            ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" up -d )
            ;;
        dev)
            info "Starting in dev mode (live backend reload, foreground)..."
            info "For frontend hot-reload, run in another terminal:"
            info "  cd frontend && npm install && npm run dev"
            echo ""
            ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f docker-compose.yml -f docker-compose.dev.yml up )
            return
            ;;
    esac

    wait_for_server
    ensure_migrated
    save_self
    print_success
}

cmd_start() {
    setup_common
    detect_socket || DOCKER_SOCK="/var/run/docker.sock"
    export DOCKER_SOCK
    fetch_standalone_compose
    ensure_data_dirs
    ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" up -d )
    wait_for_server
}

cmd_stop() {
    setup_common
    ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" down )
    ok "Biocraft-Spark stopped."
}

cmd_restart() {
    setup_common
    ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" restart )
    wait_for_server
}

cmd_logs() {
    setup_common
    ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" logs -f --tail=100 )
}

cmd_status() {
    setup_common
    ( cd "$COMPOSE_DIR" && $DOCKER_PREFIX $COMPOSE_CMD -f "$COMPOSE_FILE_NAME" ps )
}

show_help() {
    cat <<'EOF'
Biocraft-Spark installer & launcher

One-line install (no git, no Docker, no Xcode required):
  curl -fsSL https://raw.githubusercontent.com/frostlinelab/biocraft-spark/main/install.sh | bash

Usage:
  ./install.sh                Pull pre-built image and start (default)
  ./install.sh --build        Build from source and start (requires the repo)
  ./install.sh --dev          Run in dev mode with live backend reload
  ./install.sh start          Start the server
  ./install.sh stop           Stop the server
  ./install.sh restart        Restart the server
  ./install.sh logs           Tail logs (Ctrl+C to exit)
  ./install.sh status         Show container status
  ./install.sh --dir <path>   Install into <path> (default: ~/.biocraft-spark)
  ./install.sh --help         Show this help message

Platform behavior:
  - Linux without Docker: installs Docker Engine via get.docker.com automatically.
  - macOS without a runtime: installs OrbStack (Homebrew, or direct .dmg if no
    Homebrew) and launches it. OrbStack is the required runtime on macOS — see
    docs/troubleshooting.md.
  - No git/Xcode needed: only docker-compose.standalone.yml is fetched.

Prerequisites already covered by the installer:
  - A container runtime (Docker Engine on Linux, OrbStack on macOS)
  - curl (for the one-line install)
EOF
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
    local action="install"
    local build_mode="pull"

    while [ $# -gt 0 ]; do
        case "$1" in
            --build) build_mode="build"; action="install"; shift ;;
            --dev)   build_mode="dev"; action="install"; shift ;;
            --dir)   INSTALL_DIR="${2:-}"; shift 2 ;;
            start|stop|restart|logs|status) action="$1"; shift ;;
            -h|--help) show_help; exit 0 ;;
            *)
                error "Unknown argument: $1"
                echo ""
                show_help
                exit 1
                ;;
        esac
    done

    resolve_mode

    case "$action" in
        install)  cmd_install "$build_mode" ;;
        start)    cmd_start ;;
        stop)     cmd_stop ;;
        restart)  cmd_restart ;;
        logs)     cmd_logs ;;
        status)   cmd_status ;;
    esac
}

main "$@"
