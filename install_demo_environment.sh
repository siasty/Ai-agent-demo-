#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

# Disposable local demo installer for Ubuntu/Debian with systemd.
# This is intentionally not a production deployment script.

SITE_NAME="${SITE_NAME:-demo.localhost}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
BENCH_DIR="${BENCH_DIR:-${HOME}/frappe-bench}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-15}"
ERPNEXT_BRANCH="${ERPNEXT_BRANCH:-version-15}"
WORKSPACE_EMBEDDER_BRANCH="${WORKSPACE_EMBEDDER_BRANCH:-develop}"
AI_AGENT_BRANCH="${AI_AGENT_BRANCH:-main}"
WORKSPACE_EMBEDDER_REPO="${WORKSPACE_EMBEDDER_REPO:-https://github.com/siasty/workspace_embedder.git}"
AI_AGENT_REPO="${AI_AGENT_REPO:-https://github.com/siasty/Ai-agent-demo-.git}"
NODE_MAJOR="${NODE_MAJOR:-20}"
INSTALL_OLLAMA="${INSTALL_OLLAMA:-1}"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2}"
RUN_TESTS="${RUN_TESTS:-1}"
START_DEMO="${START_DEMO:-1}"
DB_ADMIN_USER="${DB_ADMIN_USER:-frappe_admin}"
DB_ADMIN_PASSWORD="${DB_ADMIN_PASSWORD:-}"
BENCH_CLI_VENV="${BENCH_CLI_VENV:-${HOME}/.local/share/frappe-bench-cli}"

readonly MODEL_PACKAGE="en-core-web-sm"
readonly MIN_NODE_MAJOR=18

log() {
    printf '\n==> %s\n' "$*"
}

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

show_help() {
    cat <<'EOF'
Usage: ./install_demo_environment.sh [--help]

Installs a disposable Frappe v15 demo on Ubuntu/Debian with systemd.
Run it as a regular user with sudo access.

Common environment variables:
  SITE_NAME=demo.localhost
  ADMIN_PASSWORD=admin
  BENCH_DIR=$HOME/frappe-bench
  INSTALL_OLLAMA=1
  OLLAMA_MODEL=llama3.2
  RUN_TESTS=1
  START_DEMO=1

Example without Ollama and without starting the server:
  INSTALL_OLLAMA=0 START_DEMO=0 ./install_demo_environment.sh
EOF
}

parse_arguments() {
    if [[ "${1:-}" == "--help" ]]; then
        show_help
        exit 0
    fi
    if (( $# > 0 )); then
        fail "Unknown argument: $1. Use --help."
    fi
}

on_error() {
    local line_number="$1"
    printf 'ERROR: installer failed near line %s.\n' "${line_number}" >&2
}

trap 'on_error "${LINENO}"' ERR

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

validate_inputs() {
    if [[ "${EUID}" -eq 0 ]]; then
        fail "Run this script as a regular user with sudo access, not as root."
    fi
    if [[ ! "${SITE_NAME}" =~ ^[A-Za-z0-9.-]+$ ]] || (( ${#SITE_NAME} > 253 )); then
        fail "SITE_NAME must be a valid hostname of at most 253 characters."
    fi
    if [[ "${SITE_NAME}" == .* || "${SITE_NAME}" == *..* || "${SITE_NAME}" == *. ]]; then
        fail "SITE_NAME cannot start or end with a dot or contain consecutive dots."
    fi
    if [[ "${SITE_NAME}" =~ (^|\.)- || "${SITE_NAME}" =~ -($|\.) ]]; then
        fail "SITE_NAME labels cannot start or end with a hyphen."
    fi
    if [[ ! "${DB_ADMIN_USER}" =~ ^[A-Za-z0-9_]+$ ]]; then
        fail "DB_ADMIN_USER may contain only letters, numbers, and underscores."
    fi
    if [[ "${ADMIN_PASSWORD}" == *$'\n'* ]]; then
        fail "ADMIN_PASSWORD cannot contain a newline."
    fi
    if [[ -n "${DB_ADMIN_PASSWORD}" && "${DB_ADMIN_PASSWORD}" =~ [\'\\] ]]; then
        fail "DB_ADMIN_PASSWORD cannot contain quotes or backslashes."
    fi
    if [[ "${DB_ADMIN_PASSWORD}" == *$'\n'* ]]; then
        fail "DB_ADMIN_PASSWORD cannot contain a newline."
    fi
    if [[ ! "${NODE_MAJOR}" =~ ^[0-9]+$ ]] || (( NODE_MAJOR < MIN_NODE_MAJOR )); then
        fail "NODE_MAJOR must be an integer greater than or equal to ${MIN_NODE_MAJOR}."
    fi
    if [[ ! "${INSTALL_OLLAMA}" =~ ^[01]$ ]]; then
        fail "INSTALL_OLLAMA must be 0 or 1."
    fi
    if [[ ! "${RUN_TESTS}" =~ ^[01]$ ]]; then
        fail "RUN_TESTS must be 0 or 1."
    fi
    if [[ ! "${START_DEMO}" =~ ^[01]$ ]]; then
        fail "START_DEMO must be 0 or 1."
    fi
    if [[ ! "${OLLAMA_MODEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*$ ]]; then
        fail "OLLAMA_MODEL contains unsupported characters."
    fi
    require_command sudo
    sudo -v
}

validate_operating_system() {
    [[ -r /etc/os-release ]] || fail "Cannot identify the operating system."
    # shellcheck disable=SC1091
    source /etc/os-release
    case "${ID}" in
        ubuntu|debian)
            ;;
        *)
            fail "Supported systems: Ubuntu and Debian. Detected: ${ID}."
            ;;
    esac
    [[ "$(ps -p 1 -o comm= | tr -d ' ')" == "systemd" ]] \
        || fail "This installer requires systemd."
}

install_system_packages() {
    local packages=(
        build-essential
        ca-certificates
        curl
        fontconfig
        git
        libffi-dev
        libjpeg-dev
        libmariadb-dev
        libssl-dev
        mariadb-client
        mariadb-server
        openssl
        pkg-config
        python3
        python3-dev
        python3-pip
        python3-venv
        redis-server
        software-properties-common
        xvfb
        zlib1g-dev
        zstd
    )

    log "Installing system packages"
    sudo apt-get update
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install --yes "${packages[@]}"
}

install_node_and_yarn() {
    local installed_major=0
    local setup_script=""
    if command -v node >/dev/null 2>&1; then
        installed_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
    fi

    if (( installed_major < MIN_NODE_MAJOR )); then
        log "Installing Node.js ${NODE_MAJOR}.x"
        setup_script="$(mktemp)"
        curl --fail --silent --show-error --location \
            "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" \
            --output "${setup_script}"
        sudo -E bash "${setup_script}"
        rm -f "${setup_script}"
        sudo apt-get install --yes nodejs
    fi

    log "Installing Yarn 1.x"
    sudo npm install --global yarn@1.22.22
    node --version
    yarn --version
}

install_bench_cli() {
    log "Installing Frappe Bench CLI"
    python3 -m venv "${BENCH_CLI_VENV}"
    "${BENCH_CLI_VENV}/bin/python" -m pip install --upgrade pip frappe-bench
    mkdir -p "${HOME}/.local/bin"
    ln -sfn "${BENCH_CLI_VENV}/bin/bench" "${HOME}/.local/bin/bench"
    export PATH="${HOME}/.local/bin:${PATH}"
    bench --version
}

configure_services() {
    log "Configuring MariaDB and Redis"
    sudo tee /etc/mysql/mariadb.conf.d/99-frappe.cnf >/dev/null <<'EOF'
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
EOF
    sudo systemctl enable mariadb redis-server
    sudo systemctl restart mariadb redis-server
    sudo systemctl is-active --quiet mariadb
    sudo systemctl is-active --quiet redis-server
}

configure_database_admin() {
    if [[ -z "${DB_ADMIN_PASSWORD}" ]]; then
        DB_ADMIN_PASSWORD="$(openssl rand -hex 24)"
    fi

    log "Creating the dedicated MariaDB setup account"
    sudo mariadb --protocol=socket <<SQL
CREATE USER IF NOT EXISTS '${DB_ADMIN_USER}'@'localhost' IDENTIFIED BY '${DB_ADMIN_PASSWORD}';
ALTER USER '${DB_ADMIN_USER}'@'localhost' IDENTIFIED BY '${DB_ADMIN_PASSWORD}';
GRANT ALL PRIVILEGES ON *.* TO '${DB_ADMIN_USER}'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL
}

install_ollama() {
    local attempt=0
    local install_script=""
    if [[ "${INSTALL_OLLAMA}" != "1" ]]; then
        log "Skipping Ollama installation (INSTALL_OLLAMA=${INSTALL_OLLAMA})"
        return
    fi

    if ! command -v ollama >/dev/null 2>&1; then
        log "Installing Ollama"
        install_script="$(mktemp)"
        curl --fail --silent --show-error --location \
            https://ollama.com/install.sh \
            --output "${install_script}"
        sh "${install_script}"
        rm -f "${install_script}"
    fi

    sudo systemctl enable --now ollama
    for attempt in $(seq 1 20); do
        if curl --fail --silent http://127.0.0.1:11434/api/version >/dev/null; then
            break
        fi
        sleep 1
    done
    curl --fail --silent --show-error http://127.0.0.1:11434/api/version >/dev/null
    log "Pulling Ollama model: ${OLLAMA_MODEL}"
    ollama pull "${OLLAMA_MODEL}"
}

run_bench() {
    (
        cd "${BENCH_DIR}"
        bench "$@"
    )
}

initialize_bench() {
    if [[ -f "${BENCH_DIR}/sites/apps.txt" ]]; then
        log "Using existing bench: ${BENCH_DIR}"
        return
    fi
    if [[ -e "${BENCH_DIR}" ]]; then
        fail "BENCH_DIR exists but is not a valid bench: ${BENCH_DIR}"
    fi

    log "Initializing Frappe ${FRAPPE_BRANCH}"
    bench init \
        --frappe-branch "${FRAPPE_BRANCH}" \
        --python "$(command -v python3)" \
        "${BENCH_DIR}"
}

ensure_app_source() {
    local app_name="$1"
    local branch="$2"
    local repository="$3"

    if [[ -d "${BENCH_DIR}/apps/${app_name}" ]]; then
        log "App source already present: ${app_name}"
        return
    fi

    log "Installing app source: ${app_name} (${branch})"
    run_bench --verbose get-app \
        --branch "${branch}" \
        --skip-assets \
        "${app_name}" \
        "${repository}"
}

install_app_sources() {
    ensure_app_source \
        "erpnext" \
        "${ERPNEXT_BRANCH}" \
        "https://github.com/frappe/erpnext"
    ensure_app_source \
        "workspace_embedder" \
        "${WORKSPACE_EMBEDDER_BRANCH}" \
        "${WORKSPACE_EMBEDDER_REPO}"
    ensure_app_source \
        "ai_agent_demo" \
        "${AI_AGENT_BRANCH}" \
        "${AI_AGENT_REPO}"
    run_bench setup requirements --python ai_agent_demo
}

create_site() {
    if [[ -f "${BENCH_DIR}/sites/${SITE_NAME}/site_config.json" ]]; then
        log "Using existing site: ${SITE_NAME}"
        run_bench use "${SITE_NAME}"
        return
    fi

    log "Creating site: ${SITE_NAME}"
    run_bench new-site \
        --db-root-username "${DB_ADMIN_USER}" \
        --db-root-password "${DB_ADMIN_PASSWORD}" \
        --admin-password "${ADMIN_PASSWORD}" \
        --set-default \
        "${SITE_NAME}"
}

install_site_apps() {
    log "Installing site apps in dependency order"
    ensure_site_app erpnext
    ensure_site_app workspace_embedder
    ensure_site_app ai_agent_demo
    run_bench --site "${SITE_NAME}" set-config developer_mode 1
    run_bench --site "${SITE_NAME}" migrate
    run_bench build --app ai_agent_demo
    run_bench --site "${SITE_NAME}" clear-cache
}

ensure_site_app() {
    local app_name="$1"
    if run_bench --site "${SITE_NAME}" list-apps --format text \
        | grep -Eq "^${app_name}([[:space:]]|$)"; then
        log "Site app already installed: ${app_name}"
        return
    fi
    run_bench --site "${SITE_NAME}" install-app "${app_name}"
}

verify_environment() {
    log "Verifying spaCy and the NER model"
    "${BENCH_DIR}/env/bin/python" -c \
        "from importlib.metadata import version; print('spaCy:', version('spacy')); print('en_core_web_sm:', version('${MODEL_PACKAGE}'))"
    "${BENCH_DIR}/env/bin/python" -c \
        "import spacy; nlp = spacy.load('en_core_web_sm'); assert 'ner' in nlp.pipe_names; print('NER pipeline:', ', '.join(nlp.pipe_names))"
    run_bench --site "${SITE_NAME}" list-apps
}

run_demo_tests() {
    if [[ "${RUN_TESTS}" != "1" ]]; then
        log "Skipping tests (RUN_TESTS=${RUN_TESTS})"
        return
    fi

    log "Running AI Agent Demo tests"
    run_bench --site "${SITE_NAME}" set-config allow_tests true
    run_bench --site "${SITE_NAME}" run-tests --app ai_agent_demo
}

configure_local_hostname() {
    local escaped_site="${SITE_NAME//./\\.}"
    if grep -Eq "(^|[[:space:]])${escaped_site}([[:space:]]|$)" /etc/hosts; then
        return
    fi
    printf '127.0.0.1 %s\n' "${SITE_NAME}" | sudo tee -a /etc/hosts >/dev/null
}

finish_installation() {
    configure_local_hostname
    log "Demo installation completed"
    printf 'URL: http://%s:8000\n' "${SITE_NAME}"
    printf 'Login: Administrator\n'
    printf 'Password: %s\n' "${ADMIN_PASSWORD}"

    if [[ "${START_DEMO}" != "1" ]]; then
        printf 'Start later with: cd %q && bench start\n' "${BENCH_DIR}"
        return
    fi

    log "Starting Frappe development server (Ctrl+C stops it)"
    cd "${BENCH_DIR}"
    exec bench start
}

main() {
    parse_arguments "$@"
    validate_inputs
    validate_operating_system
    install_system_packages
    install_node_and_yarn
    install_bench_cli
    configure_services
    configure_database_admin
    install_ollama
    initialize_bench
    install_app_sources
    create_site
    install_site_apps
    verify_environment
    run_demo_tests
    finish_installation
}

main "$@"
