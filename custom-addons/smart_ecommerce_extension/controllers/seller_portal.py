# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

import base64
import logging
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)


class SellerPortal(CustomerPortal):
    """Portal controller for Marketplace Sellers"""

    # ==========================================
    # OVERRIDE PORTAL HOME - REDIRECT SELLERS
    # ==========================================

    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        """
        Override portal home to redirect sellers directly to seller dashboard.
        Non-sellers continue to the regular portal home.
        """
        seller = self._get_current_seller()
        if seller:
            # Sellers go directly to their dashboard
            return request.redirect('/my/seller/dashboard')
        # Non-sellers get the regular portal home
        return super().home(**kw)

    def _prepare_home_portal_values(self, counters):
        """Add seller counters to portal home"""
        values = super()._prepare_home_portal_values(counters)
        
        seller = self._get_current_seller()
        if seller:
            if 'seller_product_count' in counters:
                values['seller_product_count'] = seller.product_count
            if 'seller_order_count' in counters:
                values['seller_order_count'] = seller.order_count
        
        return values

    def _get_current_seller(self):
        """Get seller record for current user"""
        if not request.env.user._is_public():
            return request.env['marketplace.seller'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
        return False

    # ==========================================
    # SELLER DASHBOARD
    # ==========================================

    @http.route(['/my/seller', '/my/seller/dashboard'], type='http', auth='user', website=True)
    def seller_dashboard(self, **kw):
        """Seller dashboard with statistics"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        # Show dashboard for all sellers (draft, pending, approved)
        # Only redirect rejected/suspended to status page
        if seller.state in ('rejected', 'suspended'):
            return request.redirect('/my/seller/status')
        
        dashboard_data = seller.get_portal_dashboard_data()
        
        # Get recent orders
        recent_orders = request.env['sale.order'].sudo().search([
            ('partner_id', '=', seller.partner_id.id),
        ], limit=5, order='date_order desc')
        
        values = {
            'page_name': 'seller_dashboard',
            'default_url': '/my/seller/dashboard',
            'seller': seller,
            'dashboard': dashboard_data,
            'recent_orders': recent_orders,
        }

        return request.render('smart_ecommerce_extension.seller_dashboard', values)
    
    @http.route('/my/seller/status', type='http', auth='user', website=True)
    def seller_request_status(self, **kw):
        """Seller request status page - shows application status for all states"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        # Calculate KYC status
        has_kyc = seller.kyc_doc or seller.kyc_document_ids
        kyc_count = len(seller.kyc_document_ids) if seller.kyc_document_ids else (1 if seller.kyc_doc else 0)
        kyc_approved = len(seller.kyc_document_ids.filtered(lambda d: d.state == 'approved')) if seller.kyc_document_ids else (1 if seller.kyc_verified else 0)
        kyc_pending = len(seller.kyc_document_ids.filtered(lambda d: d.state == 'pending')) if seller.kyc_document_ids else 0
        
        values = {
            'page_name': 'seller_status',
            'default_url': '/my/seller/status',
            'seller': seller,
            'has_kyc': has_kyc,
            'kyc_count': kyc_count,
            'kyc_approved': kyc_approved,
            'kyc_pending': kyc_pending,
        }
        
        return request.render('smart_ecommerce_extension.seller_request_status', values)

    @http.route('/my/seller/register', type='http', auth='user', website=True)
    def seller_register(self, **kw):
        """Seller registration form"""
        seller = self._get_current_seller()
        
        if seller:
            return request.redirect('/my/seller/dashboard')
        
        countries = request.env['res.country'].sudo().search([])
        
        values = {
            'page_name': 'seller_register',
            'countries': countries,
            'error': kw.get('error'),
        }
        
        return request.render('smart_ecommerce_extension.seller_register', values)

    @http.route('/my/seller/register/submit', type='http', auth='user', website=True, methods=['POST'])
    def seller_register_submit(self, **kw):
        """Process seller registration"""
        try:
            # Validate required fields
            required = ['company_name', 'phone', 'city']
            for field in required:
                if not kw.get(field):
                    return request.redirect('/my/seller/register?error=missing_fields')
            
            # Check if user already has a seller account
            existing = request.env['marketplace.seller'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            if existing:
                return request.redirect('/my/seller/dashboard')
            
            # Check company name uniqueness
            existing_company = request.env['marketplace.seller'].sudo().search([
                ('company_name', '=', kw.get('company_name'))
            ], limit=1)
            if existing_company:
                return request.redirect('/my/seller/register?error=company_exists')
            
            # Create seller
            vals = {
                'user_id': request.env.user.id,
                'company_name': kw.get('company_name'),
                'phone': kw.get('phone'),
                'city': kw.get('city'),
                'street': kw.get('street', ''),
                'tax_id': kw.get('tax_id', ''),
                'bank_name': kw.get('bank_name', ''),
                'bank_account': kw.get('bank_account', ''),
                'store_description': kw.get('store_description', ''),
                'state': 'draft',
            }
            
            if kw.get('country_id'):
                vals['country_id'] = int(kw['country_id'])
            
            seller = request.env['marketplace.seller'].sudo().create(vals)
            
            # Handle file uploads
            if kw.get('kyc_doc'):
                file_obj = kw['kyc_doc']
                if hasattr(file_obj, 'read'):
                    seller.sudo().write({
                        'kyc_doc': base64.b64encode(file_obj.read()),
                        'kyc_doc_filename': file_obj.filename if hasattr(file_obj, 'filename') else 'kyc_document',
                    })
            
            if kw.get('store_logo'):
                file_obj = kw['store_logo']
                if hasattr(file_obj, 'read'):
                    seller.sudo().write({
                        'store_logo': base64.b64encode(file_obj.read()),
                    })
            
            return request.redirect('/my/seller/dashboard?success=registered')
            
        except Exception as e:
            _logger.error(f"Seller registration error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/register?error=server_error')

    # ==========================================
    # SELLER ORDERS
    # ==========================================

    @http.route(['/my/seller/orders', '/my/seller/orders/page/<int:page>'], 
                type='http', auth='user', website=True)
    def seller_orders(self, page=1, sortby=None, filterby=None, **kw):
        """Seller orders list with pagination"""
        seller = self._get_current_seller()
        
        if not seller or seller.state != 'approved':
            return request.redirect('/my/seller/dashboard')
        
        SaleOrder = request.env['sale.order'].sudo()
        
        # Sorting
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'date_order desc'},
            'date_asc': {'label': _('Oldest'), 'order': 'date_order asc'},
            'name': {'label': _('Order #'), 'order': 'name'},
            'amount': {'label': _('Amount'), 'order': 'amount_total desc'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Filtering
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Quotation'), 'domain': [('state', '=', 'draft')]},
            'sale': {'label': _('Sales Order'), 'domain': [('state', '=', 'sale')]},
            'done': {'label': _('Done'), 'domain': [('state', '=', 'done')]},
            'cancel': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancel')]},
        }
        if not filterby:
            filterby = 'all'
        domain = searchbar_filters[filterby]['domain']
        
        # Base domain
        domain += [('partner_id', '=', seller.partner_id.id)]
        
        # Pager
        order_count = SaleOrder.search_count(domain)
        pager = portal_pager(
            url='/my/seller/orders',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=order_count,
            page=page,
            step=20
        )
        
        orders = SaleOrder.search(
            domain,
            order=order,
            limit=20,
            offset=pager['offset']
        )
        
        values = {
            'page_name': 'seller_orders',
            'default_url': '/my/seller/orders',
            'seller': seller,
            'orders': orders,
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        }

        return request.render('smart_ecommerce_extension.seller_orders', values)

    @http.route('/my/seller/orders/<int:order_id>', type='http', auth='user', website=True)
    def seller_order_detail(self, order_id, **kw):
        """View single order details"""
        seller = self._get_current_seller()
        
        if not seller or seller.state != 'approved':
            return request.redirect('/my/seller/dashboard')
        
        order = request.env['sale.order'].sudo().browse(order_id)
        
        if not order.exists() or order.partner_id.id != seller.partner_id.id:
            return request.redirect('/my/seller/orders')
        
        values = {
            'page_name': 'seller_order_detail',
            'default_url': '/my/seller/orders/%s' % order_id,
            'seller': seller,
            'order': order,
        }

        return request.render('smart_ecommerce_extension.seller_order_detail', values)

    # ==========================================
    # SELLER PAYMENTS
    # ==========================================

    @http.route(['/my/seller/payments', '/my/seller/payments/page/<int:page>'],
                type='http', auth='user', website=True)
    def seller_payments(self, page=1, **kw):
        """Seller payments/earnings history"""
        seller = self._get_current_seller()
        
        if not seller or seller.state != 'approved':
            return request.redirect('/my/seller/dashboard')
        
        payment_data = seller.get_portal_payments(page=page)
        
        # Calculate totals
        total_earnings = seller.total_sales * (1 - seller.commission_rate / 100)
        total_commission = seller.total_sales * (seller.commission_rate / 100)
        
        pager = portal_pager(
            url='/my/seller/payments',
            total=len(payment_data['payments']) * 10,  # Approximate
            page=page,
            step=20
        )
        
        values = {
            'page_name': 'seller_payments',
            'default_url': '/my/seller/payments',
            'seller': seller,
            'payments': payment_data['payments'],
            'pager': pager,
            'total_earnings': total_earnings,
            'total_commission': total_commission,
            'commission_rate': seller.commission_rate,
        }

        return request.render('smart_ecommerce_extension.seller_payments', values)

    # ==========================================
    # SELLER PROFILE
    # ==========================================

    @http.route('/my/seller/profile', type='http', auth='user', website=True)
    def seller_profile(self, **kw):
        """Seller profile edit"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        countries = request.env['res.country'].sudo().search([])
        
        values = {
            'page_name': 'seller_profile',
            'default_url': '/my/seller/profile',
            'seller': seller,
            'countries': countries,
            'success': kw.get('success'),
            'error': kw.get('error'),
        }

        return request.render('smart_ecommerce_extension.seller_profile', values)

    @http.route('/my/seller/profile/update', type='http', auth='user', website=True, methods=['POST'])
    def seller_profile_update(self, **kw):
        """Update seller profile"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        try:
            vals = {}
            
            # Editable fields
            editable_fields = ['phone', 'street', 'city', 'tax_id', 'bank_name', 
                             'bank_account', 'store_description']
            for field in editable_fields:
                if kw.get(field) is not None:
                    vals[field] = kw.get(field)
            
            if kw.get('country_id'):
                vals['country_id'] = int(kw['country_id'])
            
            # Handle file uploads
            if kw.get('kyc_doc'):
                file_obj = kw['kyc_doc']
                if hasattr(file_obj, 'read'):
                    vals['kyc_doc'] = base64.b64encode(file_obj.read())
                    vals['kyc_doc_filename'] = file_obj.filename if hasattr(file_obj, 'filename') else 'kyc_document'

            if kw.get('store_logo'):
                file_obj = kw['store_logo']
                if hasattr(file_obj, 'read'):
                    vals['store_logo'] = base64.b64encode(file_obj.read())

            if kw.get('store_banner'):
                file_obj = kw['store_banner']
                if hasattr(file_obj, 'read'):
                    vals['store_banner'] = base64.b64encode(file_obj.read())

            if vals:
                seller.sudo().write(vals)

            return request.redirect('/my/seller/profile?success=updated')
            
        except Exception as e:
            _logger.error(f"Seller profile update error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/profile?error=server_error')

    @http.route('/my/seller/submit', type='http', auth='user', website=True, methods=['POST'])
    def seller_submit_approval(self, **kw):
        """Submit seller profile for approval"""
        seller = self._get_current_seller()
        
        if not seller or seller.state != 'draft':
            return request.redirect('/my/seller/dashboard')
        
        try:
            seller.sudo().action_submit_for_approval()
            return request.redirect('/my/seller/dashboard?success=submitted')
        except Exception as e:
            _logger.error(f"Seller submit error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/dashboard?error=' + str(e))

    # ==========================================
    # SELLER DOCUMENTS MANAGEMENT
    # ==========================================

    @http.route('/my/seller/documents', type='http', auth='user', website=True)
    def seller_documents(self, **kw):
        """Manage seller KYC documents"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        document_types = request.env['marketplace.seller.kyc.document.type'].sudo().search([
            ('active', '=', True)
        ], order='sequence')
        
        # Get uploaded documents mapped by type
        uploaded_docs = {}
        for doc in seller.kyc_document_ids:
            uploaded_docs[doc.document_type_id.id] = doc
        
        values = {
            'page_name': 'seller_documents',
            'default_url': '/my/seller/documents',
            'seller': seller,
            'document_types': document_types,
            'uploaded_docs': uploaded_docs,
            'success': kw.get('success'),
            'error': kw.get('error'),
        }

        return request.render('smart_ecommerce_extension.seller_documents', values)

    @http.route('/my/seller/documents/upload', type='http', auth='user', website=True, methods=['POST'])
    def seller_documents_upload(self, **kw):
        """Upload a KYC document"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        try:
            doc_type_id = int(kw.get('document_type_id', 0))
            file_obj = kw.get('document_file')
            
            if not doc_type_id or not file_obj:
                return request.redirect('/my/seller/documents?error=missing_data')
            
            # Check if document already exists for this type
            existing_doc = seller.kyc_document_ids.filtered(
                lambda d: d.document_type_id.id == doc_type_id
            )
            
            doc_vals = {
                'seller_id': seller.id,
                'document_type_id': doc_type_id,
                'file': base64.b64encode(file_obj.read()),
                'filename': file_obj.filename if hasattr(file_obj, 'filename') else 'document',
                'state': 'pending',
            }
            
            if existing_doc:
                existing_doc.sudo().write(doc_vals)
            else:
                request.env['marketplace.seller.kyc.document'].sudo().create(doc_vals)
            
            seller.message_post(body=_('Document uploaded: %s') % request.env['marketplace.seller.kyc.document.type'].browse(doc_type_id).name)
            
            return request.redirect('/my/seller/documents?success=uploaded')
            
        except Exception as e:
            _logger.error(f"Document upload error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/documents?error=upload_failed')

    # ==========================================
    # SELLER STORE MANAGEMENT
    # ==========================================

    @http.route('/my/seller/store', type='http', auth='user', website=True)
    def seller_store_settings(self, **kw):
        """Manage store settings"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        values = {
            'page_name': 'seller_store',
            'default_url': '/my/seller/store',
            'seller': seller,
            'success': kw.get('success'),
            'error': kw.get('error'),
        }

        return request.render('smart_ecommerce_extension.seller_store_settings', values)

    @http.route('/my/seller/store/update', type='http', auth='user', website=True, methods=['POST'])
    def seller_store_update(self, **kw):
        """Update store settings"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        try:
            vals = {}
            
            # Text fields
            if kw.get('store_description') is not None:
                vals['store_description'] = kw.get('store_description')
            
            # Handle logo upload
            if kw.get('store_logo'):
                file_obj = kw.get('store_logo')
                if hasattr(file_obj, 'read'):
                    vals['store_logo'] = base64.b64encode(file_obj.read())
            
            # Handle banner upload
            if kw.get('store_banner'):
                file_obj = kw.get('store_banner')
                if hasattr(file_obj, 'read'):
                    vals['store_banner'] = base64.b64encode(file_obj.read())
            
            if vals:
                seller.sudo().write(vals)
            
            return request.redirect('/my/seller/store?success=updated')
            
        except Exception as e:
            _logger.error(f"Store update error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/store?error=update_failed')

    # ==========================================
    # SELLER PRODUCTS MANAGEMENT
    # ==========================================

    @http.route(['/my/seller/products', '/my/seller/products/page/<int:page>'],
                type='http', auth='user', website=True)
    def seller_products(self, page=1, filterby=None, **kw):
        """Seller products list"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        ProductTemplate = request.env['product.template'].sudo()
        domain = [('seller_id', '=', seller.id)]
        
        # Filters
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Draft'), 'domain': [('product_state', '=', 'draft')]},
            'pending': {'label': _('Pending'), 'domain': [('product_state', '=', 'pending')]},
            'approved': {'label': _('Approved'), 'domain': [('product_state', '=', 'approved')]},
            'rejected': {'label': _('Rejected'), 'domain': [('product_state', '=', 'rejected')]},
            'published': {'label': _('Published'), 'domain': [('is_published', '=', True)]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Pager
        product_count = ProductTemplate.search_count(domain)
        pager = portal_pager(
            url='/my/seller/products',
            url_args={'filterby': filterby},
            total=product_count,
            page=page,
            step=20
        )
        
        products = ProductTemplate.search(
            domain,
            order='create_date desc',
            limit=20,
            offset=pager['offset']
        )
        
        # Stats
        all_products = ProductTemplate.search([('seller_id', '=', seller.id)])
        stats = {
            'total': len(all_products),
            'draft': len(all_products.filtered(lambda p: p.product_state == 'draft')),
            'pending': len(all_products.filtered(lambda p: p.product_state == 'pending')),
            'approved': len(all_products.filtered(lambda p: p.product_state == 'approved')),
            'published': len(all_products.filtered(lambda p: p.is_published)),
        }
        
        values = {
            'page_name': 'seller_products',
            'default_url': '/my/seller/products',
            'seller': seller,
            'products': products,
            'pager': pager,
            'product_count': product_count,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            'stats': stats,
        }
        
        return request.render('smart_ecommerce_extension.seller_products', values)

    @http.route('/my/seller/products/new', type='http', auth='user', website=True)
    def seller_product_new(self, **kw):
        """Create new product form"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        if not seller.can_do_commercial_actions:
            return request.render('smart_ecommerce_extension.seller_not_approved', {
                'seller': seller,
                'message': _('You need to complete KYC verification before adding products.'),
            })
        
        # Get categories
        categories = request.env['marketplace.category'].sudo().search([
            ('active', '=', True)
        ], order='complete_name')
        
        values = {
            'page_name': 'seller_product_new',
            'default_url': '/my/seller/products/new',
            'seller': seller,
            'categories': categories,
            'error': kw.get('error'),
        }

        return request.render('smart_ecommerce_extension.seller_product_form', values)

    @http.route('/my/seller/products/create', type='http', auth='user', website=True, methods=['POST'])
    def seller_product_create(self, **kw):
        """Create new product"""
        seller = self._get_current_seller()
        
        if not seller or not seller.can_do_commercial_actions:
            return request.redirect('/my/seller/dashboard')
        
        try:
            # Validate required fields
            if not kw.get('name'):
                return request.redirect('/my/seller/products/new?error=name_required')
            if not kw.get('list_price') or float(kw.get('list_price', 0)) <= 0:
                return request.redirect('/my/seller/products/new?error=price_required')
            
            vals = {
                'name': kw.get('name'),
                'seller_id': seller.id,
                'list_price': float(kw.get('list_price', 0)),
                'description_sale': kw.get('description', ''),
                'brand': kw.get('brand', ''),
                'product_model': kw.get('product_model', ''),
                'seller_sku': kw.get('seller_sku', ''),
                'product_condition': kw.get('product_condition', 'new'),
                'warranty_months': int(kw.get('warranty_months', 0)),
                'product_state': 'draft',
                'sale_ok': True,
                'purchase_ok': False,
            }
            
            # Handle image upload
            if kw.get('image'):
                file_obj = kw.get('image')
                if hasattr(file_obj, 'read'):
                    vals['image_1920'] = base64.b64encode(file_obj.read())
            
            # Handle categories
            if kw.get('marketplace_categ_ids'):
                categ_ids = [int(c) for c in request.httprequest.form.getlist('marketplace_categ_ids')]
                vals['marketplace_categ_ids'] = [(6, 0, categ_ids)]
            
            product = request.env['product.template'].sudo().create(vals)
            
            return request.redirect('/my/seller/products/%s?success=created' % product.id)
            
        except Exception as e:
            _logger.error(f"Product creation error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/products/new?error=server_error')

    @http.route('/my/seller/products/<int:product_id>', type='http', auth='user', website=True)
    def seller_product_detail(self, product_id, **kw):
        """View/Edit product detail"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        product = request.env['product.template'].sudo().browse(product_id)
        
        if not product.exists() or product.seller_id.id != seller.id:
            return request.redirect('/my/seller/products')
        
        categories = request.env['marketplace.category'].sudo().search([
            ('active', '=', True)
        ], order='complete_name')
        
        values = {
            'page_name': 'seller_product_detail',
            'default_url': '/my/seller/products/%s' % product_id,
            'seller': seller,
            'product': product,
            'categories': categories,
            'success': kw.get('success'),
            'error': kw.get('error'),
        }

        return request.render('smart_ecommerce_extension.seller_product_detail', values)

    @http.route('/my/seller/products/<int:product_id>/update', type='http', auth='user', website=True, methods=['POST'])
    def seller_product_update(self, product_id, **kw):
        """Update product"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        product = request.env['product.template'].sudo().browse(product_id)
        
        if not product.exists() or product.seller_id.id != seller.id:
            return request.redirect('/my/seller/products')
        
        try:
            # Handle warranty_months with proper empty string handling
            warranty_str = kw.get('warranty_months', '0')
            warranty_months = int(warranty_str) if warranty_str else 0
            
            vals = {
                'name': kw.get('name', product.name),
                'list_price': float(kw.get('list_price', product.list_price) or 0),
                'description_sale': kw.get('description', ''),
                'brand': kw.get('brand', ''),
                'product_model': kw.get('product_model', ''),
                'seller_sku': kw.get('seller_sku', ''),
                'product_condition': kw.get('product_condition', 'new'),
                'warranty_months': warranty_months,
            }
            
            # Handle image upload
            if kw.get('image'):
                file_obj = kw.get('image')
                if hasattr(file_obj, 'read'):
                    content = file_obj.read()
                    if content:
                        vals['image_1920'] = base64.b64encode(content)
            
            # Handle categories
            if 'marketplace_categ_ids' in kw:
                categ_ids = [int(c) for c in request.httprequest.form.getlist('marketplace_categ_ids')]
                vals['marketplace_categ_ids'] = [(6, 0, categ_ids)]
            
            # If product was rejected, reset to draft on update
            if product.product_state == 'rejected':
                vals['product_state'] = 'draft'
                vals['rejection_reason'] = False
            
            # Use with_context to skip publishing validation during update
            # This allows sellers to update pending/draft products without KYC constraints
            product.with_context(skip_publishing_check=True).write(vals)
            
            return request.redirect('/my/seller/products/%s?success=updated' % product.id)
            
        except Exception as e:
            _logger.error(f"Product update error: {str(e)}", exc_info=True)
            error_msg = str(e) if len(str(e)) < 100 else 'update_failed'
            return request.redirect('/my/seller/products/%s?error=%s' % (product.id, error_msg))

    @http.route('/my/seller/products/<int:product_id>/submit', type='http', auth='user', website=True, methods=['POST'])
    def seller_product_submit(self, product_id, **kw):
        """Submit product for approval"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        product = request.env['product.template'].sudo().browse(product_id)
        
        if not product.exists() or product.seller_id.id != seller.id:
            return request.redirect('/my/seller/products')
        
        try:
            product.action_submit_for_approval()
            return request.redirect('/my/seller/products/%s?success=submitted' % product.id)
        except Exception as e:
            _logger.error(f"Product submit error: {str(e)}", exc_info=True)
            return request.redirect('/my/seller/products/%s?error=%s' % (product.id, str(e)))

    # ==========================================
    # SELLER COMMISSIONS VIEW
    # ==========================================

    @http.route(['/my/seller/commissions', '/my/seller/commissions/page/<int:page>'],
                type='http', auth='user', website=True)
    def seller_commissions(self, page=1, **kw):
        """View seller commissions"""
        seller = self._get_current_seller()
        
        if not seller:
            return request.redirect('/my/seller/register')
        
        Commission = request.env['seller.commission'].sudo()
        domain = [('seller_id', '=', seller.id)]
        
        # Pager
        commission_count = Commission.search_count(domain)
        pager = portal_pager(
            url='/my/seller/commissions',
            total=commission_count,
            page=page,
            step=20
        )
        
        commissions = Commission.search(
            domain,
            order='create_date desc',
            limit=20,
            offset=pager['offset']
        )
        
        # Calculate totals
        total_earnings = sum(commissions.mapped('seller_earnings'))
        total_pending = sum(commissions.filtered(lambda c: c.state in ('pending', 'confirmed')).mapped('seller_earnings'))
        total_paid = sum(commissions.filtered(lambda c: c.state == 'paid').mapped('seller_earnings'))
        
        values = {
            'page_name': 'seller_commissions',
            'default_url': '/my/seller/commissions',
            'seller': seller,
            'commissions': commissions,
            'pager': pager,
            'total_earnings': total_earnings,
            'total_pending': total_pending,
            'total_paid': total_paid,
            'commission_rate': seller.commission_rate,
        }

        return request.render('smart_ecommerce_extension.seller_commissions', values)

