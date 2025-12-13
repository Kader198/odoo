# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale

_logger = logging.getLogger(__name__)


class StoresController(http.Controller):
    """Public website controller for marketplace stores/sellers"""

    @http.route(['/stores', '/stores/page/<int:page>'], type='http', auth='public', website=True, sitemap=True)
    def stores_list(self, page=1, search='', **kw):
        """Display list of all active stores/sellers"""
        Seller = request.env['marketplace.seller'].sudo()
        
        # Base domain: only show approved sellers with KYC verified
        domain = [
            ('state', '=', 'approved'),
            ('can_do_commercial_actions', '=', True),
            ('active', '=', True),
        ]
        
        # Search filter
        if search:
            domain.append(('|', ('company_name', 'ilike', search), ('store_description', 'ilike', search)))
        
        # Get total count
        total_stores = Seller.search_count(domain)
        
        # Pagination
        per_page = 12
        offset = (page - 1) * per_page
        
        # Get stores
        stores = Seller.search(domain, limit=per_page, offset=offset, order='create_date desc')
        
        # Calculate pagination
        total_pages = (total_stores + per_page - 1) // per_page if total_stores > 0 else 1
        
        values = {
            'stores': stores,
            'page': page,
            'per_page': per_page,
            'total_stores': total_stores,
            'total_pages': total_pages,
            'search': search,
            'page_name': 'stores',
        }
        
        return request.render('smart_ecommerce_extension.stores_list', values)

    @http.route(['/store/<model("marketplace.seller"):seller>', 
                 '/store/<model("marketplace.seller"):seller>/page/<int:page>'], 
                type='http', auth='public', website=True, sitemap=True)
    def store_page(self, seller, page=1, **kw):
        """Display individual store page with products"""
        # Only show approved and active stores
        if seller.state != 'approved' or not seller.can_do_commercial_actions or not seller.active:
            return request.not_found()
        
        # Get published and approved products for this seller
        Product = request.env['product.template'].sudo()
        domain = [
            ('seller_id', '=', seller.id),
            ('is_published', '=', True),
            ('product_state', '=', 'approved'),
            ('sale_ok', '=', True),
            ('active', '=', True),
        ]
        
        # Get total count
        total_products = Product.search_count(domain)
        
        # Pagination
        per_page = 12
        offset = (page - 1) * per_page
        
        # Get products
        products = Product.search(domain, limit=per_page, offset=offset, order='create_date desc')
        
        # Calculate pagination
        total_pages = (total_products + per_page - 1) // per_page if total_products > 0 else 1
        
        values = {
            'seller': seller,
            'products': products,
            'page': page,
            'per_page': per_page,
            'total_products': total_products,
            'total_pages': total_pages,
            'page_name': 'store',
        }
        
        return request.render('smart_ecommerce_extension.store_page', values)
