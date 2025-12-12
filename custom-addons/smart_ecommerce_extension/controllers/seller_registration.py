# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

import base64
import logging
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class SellerRegistrationController(http.Controller):
    """Controller for public seller registration workflow"""

    # ==========================================
    # REGISTRATION FORM
    # ==========================================

    @http.route('/become-a-seller', type='http', auth='public', website=True)
    def become_seller_landing(self, **kwargs):
        """Landing page for seller registration"""
        # Check if user is already logged in and is a seller
        if request.env.user and not request.env.user._is_public():
            seller = request.env['marketplace.seller'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            if seller:
                return request.redirect('/my/seller/dashboard')
        
        return request.render('smart_ecommerce_extension.become_seller_landing', {
            'countries': request.env['res.country'].sudo().search([]),
        })

    @http.route('/seller/register', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def seller_registration_form(self, **kwargs):
        """Seller registration form"""
        # If user not logged in, redirect to signup first
        if request.env.user._is_public():
            return request.redirect('/web/signup?redirect=/seller/register')
        
        # Check if user already has a seller account
        existing_seller = request.env['marketplace.seller'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if existing_seller:
            if existing_seller.state == 'rejected':
                # Allow re-registration for rejected sellers
                pass
            else:
                return request.redirect('/my/seller/dashboard')
        
        # Get required document types
        document_types = request.env['marketplace.seller.kyc.document.type'].sudo().search([
            ('active', '=', True)
        ], order='sequence, name')
        
        countries = request.env['res.country'].sudo().search([])
        
        values = {
            'countries': countries,
            'document_types': document_types,
            'user': request.env.user,
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        }
        
        if request.httprequest.method == 'POST':
            return self._process_registration(kwargs)
        
        return request.render('smart_ecommerce_extension.seller_registration_form', values)

    def _process_registration(self, post_data):
        """Process seller registration form submission"""
        try:
            # Validate required fields
            required_fields = ['company_name', 'phone', 'city', 'terms_accepted']
            missing = [f for f in required_fields if not post_data.get(f)]
            if missing:
                raise ValidationError(_('Please fill all required fields: %s') % ', '.join(missing))
            
            if not post_data.get('terms_accepted'):
                raise ValidationError(_('You must accept the terms and conditions.'))
            
            user = request.env.user
            
            # Check for existing seller (for re-registration after rejection)
            existing_seller = request.env['marketplace.seller'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            
            # Prepare seller values
            seller_vals = {
                'user_id': user.id,
                'partner_id': user.partner_id.id,
                'company_name': post_data.get('company_name'),
                'email': user.email or post_data.get('email'),
                'phone': post_data.get('phone'),
                'city': post_data.get('city'),
                'street': post_data.get('street'),
                'country_id': int(post_data.get('country_id')) if post_data.get('country_id') else False,
                'business_type': post_data.get('business_type', 'individual'),
                'tax_id': post_data.get('tax_id'),
                'bank_name': post_data.get('bank_name'),
                'bank_account': post_data.get('bank_account'),
                'store_description': post_data.get('store_description'),
                'terms_accepted': True,
                'terms_accepted_date': fields.Datetime.now(),
                'registration_source': 'website',
                'registration_ip': request.httprequest.remote_addr,
                'state': 'draft',
                'rejection_reason': False,  # Clear previous rejection
                'kyc_rejection_reason': False,
            }
            
            if existing_seller:
                existing_seller.sudo().write(seller_vals)
                seller = existing_seller
            else:
                seller = request.env['marketplace.seller'].sudo().create(seller_vals)
            
            # Process uploaded documents
            self._process_kyc_documents(seller, post_data)
            
            # Process store logo if uploaded
            if post_data.get('store_logo'):
                logo_file = post_data.get('store_logo')
                if hasattr(logo_file, 'read'):
                    seller.sudo().write({
                        'store_logo': base64.b64encode(logo_file.read())
                    })
            
            # Log the registration
            seller.message_post(body=_('Seller registration submitted via website.'))
            
            # Send notification to admin
            self._notify_admin_new_registration(seller)
            
            return request.redirect('/seller/register/success')
            
        except ValidationError as e:
            return request.render('smart_ecommerce_extension.seller_registration_form', {
                'countries': request.env['res.country'].sudo().search([]),
                'document_types': request.env['marketplace.seller.kyc.document.type'].sudo().search([('active', '=', True)]),
                'user': request.env.user,
                'error': str(e),
                'form_data': post_data,
            })
        except Exception as e:
            _logger.exception("Seller registration error: %s", str(e))
            return request.render('smart_ecommerce_extension.seller_registration_form', {
                'countries': request.env['res.country'].sudo().search([]),
                'document_types': request.env['marketplace.seller.kyc.document.type'].sudo().search([('active', '=', True)]),
                'user': request.env.user,
                'error': _('An error occurred during registration. Please try again.'),
                'form_data': post_data,
            })

    def _process_kyc_documents(self, seller, post_data):
        """Process uploaded KYC documents"""
        from odoo import fields
        
        document_types = request.env['marketplace.seller.kyc.document.type'].sudo().search([
            ('active', '=', True)
        ])
        
        for doc_type in document_types:
            field_name = f'kyc_doc_{doc_type.id}'
            if post_data.get(field_name):
                file_obj = post_data.get(field_name)
                if hasattr(file_obj, 'read'):
                    # Check if document already exists for this type
                    existing_doc = seller.kyc_document_ids.filtered(
                        lambda d: d.document_type_id.id == doc_type.id
                    )
                    
                    doc_vals = {
                        'seller_id': seller.id,
                        'document_type_id': doc_type.id,
                        'file': base64.b64encode(file_obj.read()),
                        'filename': file_obj.filename if hasattr(file_obj, 'filename') else 'document',
                        'state': 'pending',
                        'upload_date': fields.Datetime.now(),
                    }
                    
                    if existing_doc:
                        existing_doc.sudo().write(doc_vals)
                    else:
                        request.env['marketplace.seller.kyc.document'].sudo().create(doc_vals)
        
        # Also handle legacy single KYC document field
        if post_data.get('kyc_doc'):
            file_obj = post_data.get('kyc_doc')
            if hasattr(file_obj, 'read'):
                seller.sudo().write({
                    'kyc_doc': base64.b64encode(file_obj.read()),
                    'kyc_doc_filename': file_obj.filename if hasattr(file_obj, 'filename') else 'kyc_document',
                })

    def _notify_admin_new_registration(self, seller):
        """Send notification to admin about new seller registration"""
        try:
            template = request.env.ref(
                'smart_ecommerce_extension.email_admin_new_seller_registration',
                raise_if_not_found=False
            )
            if template:
                # Get admin users
                admin_users = request.env['res.users'].sudo().search([
                    ('groups_id', 'in', request.env.ref('sales_team.group_sale_manager').id)
                ], limit=5)
                
                for admin in admin_users:
                    template.sudo().with_context(admin_email=admin.email).send_mail(
                        seller.id, force_send=True
                    )
        except Exception as e:
            _logger.warning("Failed to send admin notification: %s", str(e))

    @http.route('/seller/register/success', type='http', auth='user', website=True)
    def registration_success(self, **kwargs):
        """Registration success page"""
        seller = request.env['marketplace.seller'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        return request.render('smart_ecommerce_extension.seller_registration_success', {
            'seller': seller,
        })

    # ==========================================
    # DOCUMENT UPLOAD (POST REGISTRATION)
    # ==========================================

    @http.route('/seller/documents/upload', type='http', auth='user', website=True, methods=['POST'])
    def upload_document(self, **kwargs):
        """Upload additional KYC document"""
        from odoo import fields
        
        seller = request.env['marketplace.seller'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not seller:
            return request.redirect('/seller/register')
        
        try:
            doc_type_id = int(kwargs.get('document_type_id'))
            file_obj = kwargs.get('document_file')
            
            if not file_obj or not hasattr(file_obj, 'read'):
                raise ValidationError(_('Please select a file to upload.'))
            
            # Check if document already exists
            existing_doc = seller.kyc_document_ids.filtered(
                lambda d: d.document_type_id.id == doc_type_id
            )
            
            doc_vals = {
                'seller_id': seller.id,
                'document_type_id': doc_type_id,
                'file': base64.b64encode(file_obj.read()),
                'filename': file_obj.filename if hasattr(file_obj, 'filename') else 'document',
                'state': 'pending',
                'upload_date': fields.Datetime.now(),
                'rejection_reason': False,
            }
            
            if existing_doc:
                existing_doc.sudo().write(doc_vals)
            else:
                request.env['marketplace.seller.kyc.document'].sudo().create(doc_vals)
            
            seller.message_post(body=_('New KYC document uploaded.'))
            
        except Exception as e:
            _logger.exception("Document upload error: %s", str(e))
        
        return request.redirect('/my/seller/documents')

    # ==========================================
    # SUBMIT FOR APPROVAL
    # ==========================================

    @http.route('/seller/submit-for-approval', type='http', auth='user', website=True, methods=['POST'])
    def submit_for_approval(self, **kwargs):
        """Submit seller profile for admin approval"""
        seller = request.env['marketplace.seller'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not seller:
            return request.redirect('/seller/register')
        
        try:
            # Check if required documents are uploaded
            required_types = request.env['marketplace.seller.kyc.document.type'].sudo().search([
                ('required', '=', True)
            ])
            
            if required_types:
                submitted_types = seller.kyc_document_ids.mapped('document_type_id').ids
                missing = required_types.filtered(lambda t: t.id not in submitted_types)
                if missing:
                    missing_names = ', '.join(missing.mapped('name'))
                    raise UserError(_('Please upload required documents: %s') % missing_names)
            
            # Also check legacy KYC doc if no new documents
            if not seller.kyc_document_ids and not seller.kyc_doc:
                raise UserError(_('Please upload at least one KYC document before submitting.'))
            
            seller.sudo().write({'state': 'pending'})
            seller.message_post(body=_('Application submitted for approval.'))
            
            # Send confirmation email to seller
            template = request.env.ref(
                'smart_ecommerce_extension.email_seller_submission_confirmation',
                raise_if_not_found=False
            )
            if template:
                template.sudo().send_mail(seller.id, force_send=True)
            
            # Notify admin
            self._notify_admin_new_registration(seller)
            
        except (ValidationError, UserError) as e:
            return request.render('smart_ecommerce_extension.seller_portal_dashboard', {
                'seller': seller,
                'error': str(e),
            })
        
        return request.redirect('/my/seller/dashboard?submitted=1')
