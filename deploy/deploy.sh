#!/usr/bin/env bash
# SPT-CRM deployment script.
# Run on the target server. Supports fresh install and in-place upgrade.
#
# Quick start:
#   ./deploy.sh init       # fresh server: setup .env, pull images, migrate, seed, start all
#   ./deploy.sh upgrade    # update to latest: backup db, pull, migrate, restart
#   ./deploy.sh help       # full command list
set -euo pipefail

# -----------------------------------------------------------------------------
# Paths & defaults
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# When the script is shipped alone (CI scp's just deploy artifacts) the working
# layout is the script dir itself. When running from a full git checkout, the
# compose file lives at repo root.
if [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    WORK_DIR="$SCRIPT_DIR"
elif [ -f "$REPO_ROOT/docker-compose.prod.yml" ]; then
    WORK_DIR="$REPO_ROOT"
else
    WORK_DIR="$SCRIPT_DIR"
fi

COMPOSE_FILE="${COMPOSE_FILE:-}"
ENV_FILE="$WORK_DIR/.env"
ENV_EXAMPLE="$WORK_DIR/.env.example"
[ -f "$ENV_EXAMPLE" ] || ENV_EXAMPLE="$REPO_ROOT/.env.example"

BACKUP_DIR="${BACKUP_DIR:-$WORK_DIR/backups}"
HARBOR_REGISTRY="${HARBOR_REGISTRY:-wmharbor.fourier.net.cn:39011}"

BUILD_LOCAL=0
WITH_DEMO=0
NON_INTERACTIVE=0
SKIP_BACKUP=0

# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------
log()    { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
ok()     { printf '\033[1;32m[ ok  ]\033[0m %s\n' "$*"; }
warn()   { printf '\033[1;33m[warn ]\033[0m %s\n' "$*" >&2; }
err()    { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }
die()    { err "$*"; exit 1; }

# -----------------------------------------------------------------------------
# Compose detection (v1 docker-compose vs v2 docker compose)
# -----------------------------------------------------------------------------
detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE=(docker-compose)
    else
        die "Neither 'docker compose' nor 'docker-compose' is available. Install Docker Engine 20.10+ with the compose plugin."
    fi
}

resolve_compose_file() {
    if [ -n "$COMPOSE_FILE" ] && [ -f "$COMPOSE_FILE" ]; then return; fi
    for candidate in \
        "$WORK_DIR/docker-compose.yml" \
        "$WORK_DIR/docker-compose.prod.yml" \
        "$REPO_ROOT/docker-compose.prod.yml"; do
        if [ -f "$candidate" ]; then COMPOSE_FILE="$candidate"; return; fi
    done
    die "No compose file found. Place docker-compose.yml next to this script or run from repo root."
}

dc() {
    "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

# -----------------------------------------------------------------------------
# Prerequisite checks
# -----------------------------------------------------------------------------
check_prereqs() {
    command -v docker >/dev/null 2>&1 || die "Docker is not installed."
    docker info >/dev/null 2>&1 || die "Cannot reach the Docker daemon. Is the user in the 'docker' group?"
    detect_compose
    resolve_compose_file
    ok "docker: $(docker --version)"
    ok "compose: ${COMPOSE[*]}"
    ok "compose file: $COMPOSE_FILE"
}

# -----------------------------------------------------------------------------
# .env management
# -----------------------------------------------------------------------------
gen_secret() { openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '\n=+/' | cut -c1-48; }

ensure_env_file() {
    if [ -f "$ENV_FILE" ]; then ok ".env exists at $ENV_FILE"; return; fi
    [ -f "$ENV_EXAMPLE" ] || die ".env.example not found (looked at $ENV_EXAMPLE). Cannot bootstrap .env."

    log "Creating .env from template..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"

    if [ "$NON_INTERACTIVE" -eq 1 ]; then
        # CI / scripted: auto-generate secrets, leave the rest to the operator.
        sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen_secret)|" "$ENV_FILE"
        sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(gen_secret)|" "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
        warn "Non-interactive: auto-generated POSTGRES_PASSWORD and JWT_SECRET_KEY. Review $ENV_FILE before exposing the system."
        return
    fi

    echo
    echo "==> Configure required secrets (press Enter to auto-generate)"
    read -rp "  POSTGRES_PASSWORD: " pg_pw
    read -rp "  JWT_SECRET_KEY:    " jwt_key
    read -rp "  CORS_ORIGINS (e.g. https://crm.example.com): " cors
    [ -z "$pg_pw" ] && pg_pw="$(gen_secret)" && echo "  -> generated POSTGRES_PASSWORD"
    [ -z "$jwt_key" ] && jwt_key="$(gen_secret)" && echo "  -> generated JWT_SECRET_KEY"

    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$pg_pw|" "$ENV_FILE"
    sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$jwt_key|" "$ENV_FILE"
    [ -n "$cors" ] && sed -i.bak "s|^CORS_ORIGINS=.*|CORS_ORIGINS=$cors|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
    chmod 600 "$ENV_FILE"
    ok "Wrote $ENV_FILE (mode 600). Edit it to tune AI / encryption keys later."
}

# -----------------------------------------------------------------------------
# Image lifecycle
# -----------------------------------------------------------------------------
fetch_images() {
    if [ "$BUILD_LOCAL" -eq 1 ]; then
        [ -d "$REPO_ROOT/backend" ] && [ -d "$REPO_ROOT/frontend" ] \
            || die "--build requires the full source tree (backend/ and frontend/) at $REPO_ROOT."
        local be_tag="$HARBOR_REGISTRY/hengchao-dev/spt-crm-backend:latest"
        local fe_tag="$HARBOR_REGISTRY/hengchao-dev/spt-crm-frontend:latest"
        log "Building images locally and tagging as $be_tag / $fe_tag..."
        docker build -t "$be_tag" "$REPO_ROOT/backend"
        docker build -t "$fe_tag" "$REPO_ROOT/frontend"
        ok "Local images tagged to match compose references; no registry pull needed."
        return
    fi

    log "Pulling images from $HARBOR_REGISTRY..."
    if ! docker pull "$HARBOR_REGISTRY/hengchao-dev/spt-crm-backend:latest" >/dev/null 2>&1; then
        warn "Cannot pull from $HARBOR_REGISTRY. You may need: docker login $HARBOR_REGISTRY"
        if [ "$NON_INTERACTIVE" -eq 0 ]; then
            read -rp "Login to Harbor now? [y/N] " ans
            [[ "$ans" =~ ^[Yy]$ ]] && docker login "$HARBOR_REGISTRY"
        fi
    fi
    dc pull
}

# -----------------------------------------------------------------------------
# Database lifecycle
# -----------------------------------------------------------------------------
wait_for_db() {
    log "Waiting for database to accept connections..."
    for i in $(seq 1 60); do
        if dc exec -T db pg_isready -U postgres >/dev/null 2>&1; then
            ok "Database is ready."
            return
        fi
        sleep 2
    done
    die "Database did not become ready within 120s. Check: $0 logs db"
}

run_migrations() {
    log "Running alembic upgrade head..."
    dc run --rm backend alembic upgrade head
    ok "Migrations applied."
}

run_seed() {
    if [ "$WITH_DEMO" -eq 1 ]; then
        log "Seeding database (with demo data — customers, projects)..."
        dc run --rm backend python -m scripts.seed
    else
        log "Seeding database (production: permissions, roles, admin user)..."
        dc run --rm backend python seed.py
    fi

    # Lead classification data dictionary (issue #17): customer_type + industry options.
    # Idempotent — safe on every install/upgrade.
    log "Seeding lead classification dictionary (customer_type + industry)..."
    dc run --rm backend python -m scripts.seed_lead_dicts

    ok "Seed complete. All seed scripts are idempotent — safe to re-run."
}

backup_db() {
    [ "$SKIP_BACKUP" -eq 1 ] && { warn "Skipping backup (--skip-backup)."; return; }
    mkdir -p "$BACKUP_DIR"
    local ts ; ts="$(date +%Y%m%d-%H%M%S)"
    local out="$BACKUP_DIR/spt_crm-$ts.sql.gz"
    log "Backing up database to $out..."
    if ! dc ps db --status running -q | grep -q .; then
        warn "db service is not running — nothing to back up."
        return
    fi
    dc exec -T db pg_dump -U postgres -Fc spt_crm | gzip > "$out"
    ok "Backup written: $out ($(du -h "$out" | cut -f1))"
}

restore_db() {
    local file="${1:-}"
    [ -n "$file" ] || die "Usage: $0 restore <backup-file.sql.gz>"
    [ -f "$file" ] || die "Backup file not found: $file"
    if [ "$NON_INTERACTIVE" -eq 0 ]; then
        read -rp "This will DROP and recreate the spt_crm database from $file. Continue? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]] || die "Aborted."
    fi
    log "Restoring from $file..."
    dc stop backend worker reminder >/dev/null 2>&1 || true
    dc exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS spt_crm;"
    dc exec -T db psql -U postgres -c "CREATE DATABASE spt_crm;"
    gunzip -c "$file" | dc exec -T db pg_restore -U postgres -d spt_crm --no-owner --no-acl
    dc start backend worker reminder
    ok "Restore complete."
}

# -----------------------------------------------------------------------------
# Top-level commands
# -----------------------------------------------------------------------------
cmd_init() {
    log "=== Fresh install ==="
    check_prereqs
    ensure_env_file
    fetch_images

    log "Starting database..."
    dc up -d db
    wait_for_db

    run_migrations
    run_seed

    log "Starting backend, workers, and frontend..."
    dc up -d
    sleep 3
    dc ps

    cat <<EOF

$(ok "Install complete.")

  Frontend:  http://<server-ip>:8010
  HTTPS:     https://<server-ip>:8410   (mounts /etc/letsencrypt; install certs first)
  Backend:   container 'backend' on port 8002 (proxied by nginx)

  Default admin login:
    username: admin
    password: admin123  (CHANGE IT IMMEDIATELY in the UI)

  Useful commands:
    $0 status              # container status
    $0 logs backend        # tail backend logs
    $0 upgrade             # pull latest images and migrate
    $0 backup              # snapshot the database
EOF
}

cmd_upgrade() {
    log "=== Upgrade ==="
    check_prereqs
    [ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE — run '$0 init' first."

    backup_db
    fetch_images

    log "Recreating backend & workers with new image..."
    dc up -d --no-deps db
    wait_for_db
    run_migrations
    run_seed
    dc up -d --force-recreate backend worker reminder frontend
    sleep 3
    dc ps
    ok "Upgrade complete."
}

cmd_status()  { check_prereqs; dc ps; }
cmd_logs()    { check_prereqs; dc logs --tail=200 -f "${1:-}"; }
cmd_down()    { check_prereqs; dc down; }
cmd_restart() { check_prereqs; dc restart "${1:-}"; }
cmd_seed()    { check_prereqs; run_seed; }
cmd_migrate() { check_prereqs; run_migrations; }
cmd_backup()  { check_prereqs; backup_db; }
cmd_restore() { check_prereqs; restore_db "${1:-}"; }

usage() {
    cat <<EOF
SPT-CRM deployment script

Usage: $0 <command> [options]

Commands:
  init                Fresh install on a new server (env setup → migrate → seed → start)
  upgrade             Backup db, pull latest images, run migrations, restart services
  status              Show container status
  logs [service]      Tail logs (default: all services)
  restart [service]   Restart a service (default: all)
  down                Stop and remove all containers (volumes preserved)
  migrate             Run alembic upgrade head only
  seed                Run seed only (idempotent)
  backup              pg_dump the database to ./backups/
  restore <file>      Restore database from a backup file
  help                Show this help

Options (must come AFTER the command):
  --build             Build images locally instead of pulling from Harbor (needs source tree)
  --with-demo         Seed demo data (customers, projects). Default: production seed only
  --non-interactive   Don't prompt; auto-generate secrets, accept defaults
  --skip-backup       Skip the pre-upgrade db backup (use with care)

Environment overrides:
  COMPOSE_FILE        Path to compose file (auto-detected by default)
  BACKUP_DIR          Where to write pg_dump output (default: ./backups)
  HARBOR_REGISTRY     Override registry host (default: wmharbor.fourier.net.cn:39011)

Examples:
  ./deploy.sh init                          # full interactive install
  ./deploy.sh init --non-interactive        # CI / unattended install
  ./deploy.sh init --build                  # build images from source instead of pulling
  ./deploy.sh init --with-demo              # include demo customers/projects
  ./deploy.sh upgrade                       # standard upgrade with backup
  ./deploy.sh upgrade --skip-backup         # fast upgrade (only after a manual backup)
  ./deploy.sh logs backend                  # follow backend logs
  ./deploy.sh restore backups/spt_crm-20260427-140000.sql.gz
EOF
}

# -----------------------------------------------------------------------------
# Arg parsing
# -----------------------------------------------------------------------------
[ $# -eq 0 ] && { usage; exit 1; }
COMMAND="$1"; shift

POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --build)            BUILD_LOCAL=1 ;;
        --with-demo)        WITH_DEMO=1 ;;
        --non-interactive)  NON_INTERACTIVE=1 ;;
        --skip-backup)      SKIP_BACKUP=1 ;;
        -h|--help)          usage; exit 0 ;;
        *)                  POSITIONAL+=("$1") ;;
    esac
    shift
done

case "$COMMAND" in
    init)     cmd_init ;;
    upgrade)  cmd_upgrade ;;
    status)   cmd_status ;;
    logs)     cmd_logs "${POSITIONAL[@]:-}" ;;
    restart)  cmd_restart "${POSITIONAL[@]:-}" ;;
    down)     cmd_down ;;
    migrate)  cmd_migrate ;;
    seed)     cmd_seed ;;
    backup)   cmd_backup ;;
    restore)  cmd_restore "${POSITIONAL[@]:-}" ;;
    help|-h|--help) usage ;;
    *)        err "Unknown command: $COMMAND"; usage; exit 1 ;;
esac
