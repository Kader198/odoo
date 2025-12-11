#!/bin/bash

# ============================================================
# Odoo Development Server Launcher
# ============================================================
# Usage:
#   ./run_odoo.sh                  - Start Odoo normally
#   ./run_odoo.sh -u MODULE        - Upgrade specific module(s)
#   ./run_odoo.sh -i MODULE        - Install specific module(s)
#   ./run_odoo.sh --fresh          - Clear all cache and start fresh
#   ./run_odoo.sh --init-demo      - Initialize database with demo data
#   ./run_odoo.sh --clear-cache    - Only clear cache, don't start
#   ./run_odoo.sh --install-custom - Install all custom-addons modules
#   ./run_odoo.sh --upgrade-custom - Upgrade all custom-addons modules
# ============================================================

set -e

# Configuration
ODOO_DIR="/Users/abdelkader/odoo-dev/odoo"
CUSTOM_ADDONS_DIR="$ODOO_DIR/custom-addons"
CONFIG_FILE="myodoo.cfg"
DATA_DIR="/Users/abdelkader/Library/Application Support/Odoo"
VENV_DIR="venv"
DB_NAME="odoo_db"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Stop all running Odoo instances
stop_odoo() {
    log_info "Stopping all running Odoo instances..."
    pkill -f "odoo-bin" 2>/dev/null || true
    pkill -f "python.*odoo-bin" 2>/dev/null || true
    sleep 2
    
    # Force kill if still running
    if pgrep -f "odoo-bin" > /dev/null 2>&1; then
        log_warning "Force killing remaining Odoo processes..."
        pkill -9 -f "odoo-bin" 2>/dev/null || true
        sleep 1
    fi
    log_success "All Odoo processes stopped"
}

# Clear Python cache
clear_python_cache() {
    log_info "Clearing Python cache (__pycache__)..."
    find "$ODOO_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$ODOO_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$ODOO_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
    log_success "Python cache cleared"
}

# Clear Odoo assets cache
clear_odoo_assets() {
    log_info "Clearing Odoo assets cache..."
    
    # Clear filestore assets if exists
    if [ -d "$DATA_DIR/filestore/$DB_NAME" ]; then
        # Remove web assets from filestore
        find "$DATA_DIR/filestore/$DB_NAME" -name "web_*" -type d -exec rm -rf {} + 2>/dev/null || true
    fi
    
    # Clear sessions
    if [ -d "$DATA_DIR/sessions" ]; then
        rm -rf "$DATA_DIR/sessions/"* 2>/dev/null || true
        log_info "Sessions cleared"
    fi
    
    log_success "Odoo assets cache cleared"
}

# Clear all caches
clear_all_cache() {
    log_info "========================================="
    log_info "Clearing all caches..."
    log_info "========================================="
    clear_python_cache
    clear_odoo_assets
    log_success "All caches cleared!"
}

# Activate virtual environment
activate_venv() {
    if [ -d "$ODOO_DIR/$VENV_DIR" ]; then
        source "$ODOO_DIR/$VENV_DIR/bin/activate"
        log_success "Virtual environment activated"
    else
        log_error "Virtual environment not found at $ODOO_DIR/$VENV_DIR"
        exit 1
    fi
}

# Get all custom-addons module names
get_custom_modules() {
    local modules=""
    
    # Find all directories containing __manifest__.py in custom-addons
    for dir in "$CUSTOM_ADDONS_DIR"/*/; do
        if [ -f "${dir}__manifest__.py" ]; then
            module_name=$(basename "$dir")
            if [ -n "$modules" ]; then
                modules="${modules},${module_name}"
            else
                modules="$module_name"
            fi
        fi
    done
    
    echo "$modules"
}

# Install all custom-addons modules
install_custom_modules() {
    local modules=$(get_custom_modules)
    
    if [ -z "$modules" ]; then
        log_error "No custom modules found in $CUSTOM_ADDONS_DIR"
        exit 1
    fi
    
    log_info "========================================="
    log_info "Installing ALL custom-addons modules"
    log_info "========================================="
    log_info "Modules: $modules"
    log_info "========================================="
    
    cd "$ODOO_DIR"
    activate_venv
    
    python3 odoo-bin --config="$CONFIG_FILE" -i "$modules" --stop-after-init
    
    log_success "All custom modules installed!"
    log_info "Starting Odoo server..."
    
    python3 odoo-bin --config="$CONFIG_FILE"
}

# Upgrade all custom-addons modules
upgrade_custom_modules() {
    local modules=$(get_custom_modules)
    
    if [ -z "$modules" ]; then
        log_error "No custom modules found in $CUSTOM_ADDONS_DIR"
        exit 1
    fi
    
    log_info "========================================="
    log_info "Upgrading ALL custom-addons modules"
    log_info "========================================="
    log_info "Modules: $modules"
    log_info "========================================="
    
    cd "$ODOO_DIR"
    activate_venv
    
    python3 odoo-bin --config="$CONFIG_FILE" -u "$modules" --stop-after-init
    
    log_success "All custom modules upgraded!"
    log_info "Starting Odoo server..."
    
    python3 odoo-bin --config="$CONFIG_FILE"
}

# List all custom-addons modules
list_custom_modules() {
    log_info "========================================="
    log_info "Custom-addons modules:"
    log_info "========================================="
    
    for dir in "$CUSTOM_ADDONS_DIR"/*/; do
        if [ -f "${dir}__manifest__.py" ]; then
            module_name=$(basename "$dir")
            echo -e "  ${GREEN}✓${NC} $module_name"
        fi
    done
    
    echo ""
    log_info "Comma-separated list:"
    echo "  $(get_custom_modules)"
    echo ""
}

# Start Odoo
start_odoo() {
    local extra_args="$@"
    
    cd "$ODOO_DIR"
    activate_venv
    
    log_info "========================================="
    log_info "Starting Odoo Server"
    log_info "========================================="
    log_info "Config: $CONFIG_FILE"
    log_info "Database: $DB_NAME"
    if [ -n "$extra_args" ]; then
        log_info "Extra args: $extra_args"
    fi
    log_info "========================================="
    
    # Start Odoo with any extra arguments
    python3 odoo-bin --config="$CONFIG_FILE" $extra_args
}

# Initialize database with demo data (SAFE - only if DB doesn't exist)
init_with_demo() {
    log_info "========================================="
    log_info "Initializing database with demo data..."
    log_info "========================================="
    
    cd "$ODOO_DIR"
    activate_venv
    
    # Check if database exists
    if psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        log_warning "Database '$DB_NAME' already exists!"
        log_warning "This command will only install modules on existing database."
        log_warning "To create a fresh database, manually drop it first: dropdb $DB_NAME"
        log_info "Installing base modules with demo data on existing database..."
    else
        log_info "Database '$DB_NAME' does not exist. Creating new database..."
        createdb "$DB_NAME" || {
            log_error "Failed to create database"
            exit 1
        }
        log_success "Database created successfully!"
        log_info "Installing base modules with demo data..."
    fi
    
    python3 odoo-bin --config="$CONFIG_FILE" \
        -d "$DB_NAME" \
        -i base,sale,website,website_sale,stock,purchase \
        --load-language=en_US \
        --without-demo=False \
        --stop-after-init
    
    log_success "Database initialized with demo data!"
    log_info "Starting Odoo server..."
    
    python3 odoo-bin --config="$CONFIG_FILE"
}

# Show help
show_help() {
    echo "Odoo Development Server Launcher"
    echo ""
    echo "Usage: ./run_odoo.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (no args)         Start Odoo normally"
    echo "  -u MODULE         Upgrade module(s) - comma separated for multiple"
    echo "  -i MODULE         Install module(s) - comma separated for multiple"
    echo "  --fresh           Clear all cache and start fresh"
    echo "  --init-demo       Initialize database with demo data (SAFE - only if DB doesn't exist)"
    echo "  --clear-cache     Only clear cache, don't start Odoo"
    echo "  --install-custom  Install ALL custom-addons modules"
    echo "  --upgrade-custom  Upgrade ALL custom-addons modules"
    echo "  --list-custom     List all custom-addons modules"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_odoo.sh                              # Start Odoo"
    echo "  ./run_odoo.sh -u smart_ecommerce_extension # Upgrade single module"
    echo "  ./run_odoo.sh --install-custom             # Install all custom modules"
    echo "  ./run_odoo.sh --fresh --upgrade-custom     # Clear cache + upgrade all"
    echo "  ./run_odoo.sh --init-demo                  # Fresh DB with demo data"
    echo ""
}

# ============================================================
# Main Script Logic
# ============================================================

# Parse arguments
CLEAR_CACHE=false
INIT_DEMO=false
INSTALL_CUSTOM=false
UPGRADE_CUSTOM=false
EXTRA_ARGS=""

# Check for --list-custom first (no need to stop Odoo)
for arg in "$@"; do
    if [ "$arg" = "--list-custom" ]; then
        list_custom_modules
        exit 0
    fi
    if [ "$arg" = "-h" ] || [ "$arg" = "--help" ]; then
        show_help
        exit 0
    fi
done

# Always stop running instances first
stop_odoo

while [[ $# -gt 0 ]]; do
    case $1 in
        --fresh)
            CLEAR_CACHE=true
            shift
            ;;
        --clear-cache)
            clear_all_cache
            log_success "Cache cleared. Exiting without starting Odoo."
            exit 0
            ;;
        --init-demo)
            INIT_DEMO=true
            shift
            ;;
        --install-custom)
            INSTALL_CUSTOM=true
            shift
            ;;
        --upgrade-custom)
            UPGRADE_CUSTOM=true
            shift
            ;;
        --list-custom)
            # Already handled above
            shift
            ;;
        -h|--help)
            # Already handled above
            shift
            ;;
        -u|-i)
            EXTRA_ARGS="$EXTRA_ARGS $1 $2"
            shift 2
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# Clear cache if requested
if [ "$CLEAR_CACHE" = true ]; then
    clear_all_cache
fi

# Handle different modes
if [ "$INIT_DEMO" = true ]; then
    clear_all_cache
    init_with_demo
elif [ "$INSTALL_CUSTOM" = true ]; then
    install_custom_modules
elif [ "$UPGRADE_CUSTOM" = true ]; then
    upgrade_custom_modules
else
    start_odoo $EXTRA_ARGS
fi
