Contributing to Odoo
./run_odoo.sh	Start Odoo normally
./run_odoo.sh -u MODULE	Upgrade specific module(s)
./run_odoo.sh -i MODULE	Install specific module(s) 
./run_odoo.sh --fresh	Clear all cache and start fresh
./run_odoo.sh --init-demo	Initialize DB with demo data (RESETS DB!)
./run_odoo.sh --clear-cache	Only clear cache, don't start
./run_odoo.sh --install-custom	Install ALL custom-addons modules
./run_odoo.sh --upgrade-custom	Upgrade ALL custom-addons modules
./run_odoo.sh --list-custom	List all custom-addons modules


# Fresh start with module upgrade (clears cache first)
./run_odoo.sh --fresh -u smart_ecommerce_extension

# Upgrade multiple modules
./run_odoo.sh -u smart_ecommerce_extension,smart_marketplace_core

# Complete fresh database with demo data
./run_odoo.sh --init-demo

# Just clear cache without starting
./run_odoo.sh --clear-cache


# List all custom-addons modules
./run_odoo.sh --list-custom

# Install ALL custom-addons modules
./run_odoo.sh --install-custom

# Upgrade ALL custom-addons modules  
./run_odoo.sh --upgrade-custom

# Clear cache + upgrade all custom modules
./run_odoo.sh --fresh --upgrade-custom


./run_odoo.sh --fresh -u smart_ecommerce_extension




