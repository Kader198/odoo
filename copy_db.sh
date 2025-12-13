#!/bin/bash
#
# Database Copy Script
# Creates a copy of a PostgreSQL database
#
# Usage: ./copy_db.sh <source_db> [target_db]
#
# If target_db is not provided, it will create: source_db_copy_YYYYMMDD_HHMMSS
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if source database is provided
if [ -z "$1" ]; then
    print_error "Usage: $0 <source_db> [target_db]"
    echo ""
    echo "Examples:"
    echo "  $0 odoo_db                    # Creates odoo_db_copy_20251213_161200"
    echo "  $0 odoo_db my_backup          # Creates my_backup"
    echo "  $0 odoo_db odoo_db_staging    # Creates odoo_db_staging"
    exit 1
fi

SOURCE_DB="$1"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Set target database name
if [ -z "$2" ]; then
    TARGET_DB="${SOURCE_DB}_copy_${TIMESTAMP}"
else
    TARGET_DB="$2"
fi

print_info "==========================================="
print_info "Database Copy Script"
print_info "==========================================="
print_info "Source Database: ${SOURCE_DB}"
print_info "Target Database: ${TARGET_DB}"
print_info "==========================================="

# Check if source database exists
if ! psql -lqt | cut -d \| -f 1 | grep -qw "$SOURCE_DB"; then
    print_error "Source database '$SOURCE_DB' does not exist!"
    echo ""
    echo "Available databases:"
    psql -lqt | cut -d \| -f 1 | grep -v "^$" | sed 's/^/  /'
    exit 1
fi

# Check if target database already exists
if psql -lqt | cut -d \| -f 1 | grep -qw "$TARGET_DB"; then
    print_warning "Target database '$TARGET_DB' already exists!"
    read -p "Do you want to drop it and create a new copy? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        print_info "Dropping existing database '$TARGET_DB'..."
        
        # Terminate connections to target database
        psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TARGET_DB' AND pid <> pg_backend_pid();" postgres 2>/dev/null || true
        
        dropdb "$TARGET_DB"
        print_success "Dropped existing database '$TARGET_DB'"
    else
        print_info "Operation cancelled."
        exit 0
    fi
fi

# Terminate all connections to source database (required for template copy)
print_info "Terminating active connections to '$SOURCE_DB'..."
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$SOURCE_DB' AND pid <> pg_backend_pid();" postgres 2>/dev/null || true

# Create database copy using template
print_info "Creating database copy..."
print_info "This may take a while for large databases..."

if createdb -T "$SOURCE_DB" "$TARGET_DB"; then
    print_success "==========================================="
    print_success "Database copied successfully!"
    print_success "==========================================="
    print_success "New database: $TARGET_DB"
    echo ""
    
    # Show database size
    SIZE=$(psql -t -c "SELECT pg_size_pretty(pg_database_size('$TARGET_DB'));" postgres 2>/dev/null | xargs)
    print_info "Database size: $SIZE"
    
    echo ""
    print_info "To use the new database with Odoo:"
    echo "  ./odoo-bin -c myodoo.cfg -d $TARGET_DB"
    echo ""
    print_info "To connect directly with psql:"
    echo "  psql -d $TARGET_DB"
else
    print_error "Failed to copy database!"
    exit 1
fi

