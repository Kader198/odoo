# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MarketplaceSeller(models.Model):
    _inherit = 'marketplace.seller'
    _order = 'name'

    name = fields.Char(
        string='Seller Name',
        compute='_compute_name',
        store=True,
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User Account',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='The user account associated with this seller',
    )
    # partner_id is inherited from smart_marketplace_core (required field)
    # We populate it automatically from user_id via create/write/onchange methods
    company_name = fields.Char(
        string='Company/Store Name',
        required=True,
        tracking=True,
        help='The business name displayed to customers',
    )
    
    # Contact Information
    email = fields.Char(
        related='partner_id.email',
        readonly=False,
        store=True,
    )
    phone = fields.Char(
        related='partner_id.phone',
        readonly=False,
        store=True,
    )
    street = fields.Char(related='partner_id.street', readonly=False)
    city = fields.Char(related='partner_id.city', readonly=False)
    country_id = fields.Many2one(related='partner_id.country_id', readonly=False)
    
    # KYC Documents
    kyc_doc = fields.Binary(
        string='KYC Document',
        attachment=True,
        help='Identity verification document (ID card, passport, business license)',
    )
    kyc_doc_filename = fields.Char(string='KYC Document Filename')
    kyc_verified = fields.Boolean(
        string='KYC Verified',
        default=False,
        tracking=True,
    )
    kyc_verified_date = fields.Date(
        string='KYC Verification Date',
        readonly=True,
    )
    kyc_verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        readonly=True,
    )
    kyc_rejection_reason = fields.Text(
        string='KYC Rejection Reason',
        tracking=True,
    )
    
    # ==========================================
    # KYC STATUS COMPUTED FIELDS
    # ==========================================
    
    can_do_commercial_actions = fields.Boolean(
        string='Can Do Commercial Actions',
        compute='_compute_can_do_commercial_actions',
        store=True,
        help='Indicates if seller can publish products, manage orders, and perform commercial actions. '
             'Requires both approval and KYC verification.',
    )
    
    kyc_status = fields.Selection([
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], string='KYC Status', compute='_compute_kyc_status', store=True)
    
    commercial_status_message = fields.Char(
        string='Commercial Status',
        compute='_compute_commercial_status_message',
        help='Message explaining why commercial actions may be restricted',
    )
    
    # Business Documents
    business_license = fields.Binary(
        string='Business License',
        attachment=True,
    )
    business_license_filename = fields.Char(string='License Filename')
    tax_id = fields.Char(string='Tax ID / VAT Number')
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    rejection_reason = fields.Text(string='Rejection Reason')
    suspension_reason = fields.Text(string='Suspension Reason')
    
    # Financial Information
    bank_account = fields.Char(string='Bank Account Number')
    bank_name = fields.Char(string='Bank Name')
    commission_rate = fields.Float(
        string='Commission Rate (%)',
        default=10.0,
        help='Platform commission percentage on each sale',
    )
    
    # Products and Orders - One2many relationships
    product_ids = fields.One2many(
        'product.template',
        'seller_id',
        string='Products',
        help='Products owned by this seller',
    )
    
    # Statistics (Computed)
    product_count = fields.Integer(
        string='Products',
        compute='_compute_statistics',
    )
    order_count = fields.Integer(
        string='Orders',
        compute='_compute_statistics',
    )
    total_sales = fields.Monetary(
        string='Total Sales',
        compute='_compute_statistics',
        currency_field='currency_id',
    )
    rating = fields.Float(
        string='Rating',
        default=0.0,
        digits=(2, 1),
    )
    # currency_id is inherited from smart_marketplace_core as related field
    
    # Timestamps
    approved_date = fields.Datetime(string='Approved Date', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    
    # Store Settings
    store_description = fields.Html(string='Store Description')
    store_logo = fields.Binary(string='Store Logo', attachment=True)
    store_banner = fields.Binary(string='Store Banner', attachment=True)
    
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('user_unique', 'UNIQUE(user_id)', 'A user can only have one seller account!'),
        ('company_name_unique', 'UNIQUE(company_name)', 'This store name is already taken!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set required fields before validation"""
        for vals in vals_list:
            user = None
            # If user_id is set, get the user record
            if vals.get('user_id'):
                user = self.env['res.users'].browse(vals['user_id'])
                # Set partner_id from user if not already set
                if not vals.get('partner_id') and user.exists() and user.partner_id:
                    vals['partner_id'] = user.partner_id.id
            
            # Set name if not already set (required field)
            if not vals.get('name'):
                if vals.get('company_name'):
                    vals['name'] = vals['company_name']
                elif user and user.exists():
                    vals['name'] = user.name
                else:
                    vals['name'] = _('New Seller')
        
        return super().create(vals_list)

    def write(self, vals):
        """Override write to update related fields when user_id or company_name changes"""
        # Update partner_id when user_id changes
        if vals.get('user_id'):
            user = self.env['res.users'].browse(vals['user_id'])
            if user.exists() and user.partner_id:
                vals['partner_id'] = user.partner_id.id
        
        # Update name when company_name changes
        if vals.get('company_name'):
            vals['name'] = vals['company_name']
        
        return super().write(vals)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Update partner_id and name when user is changed in the form"""
        if self.user_id:
            self.partner_id = self.user_id.partner_id
            if not self.company_name:
                self.name = self.user_id.name

    @api.onchange('company_name')
    def _onchange_company_name(self):
        """Update name when company_name is changed"""
        if self.company_name:
            self.name = self.company_name

    @api.depends('user_id', 'company_name')
    def _compute_name(self):
        for seller in self:
            if seller.company_name:
                seller.name = seller.company_name
            elif seller.user_id:
                seller.name = seller.user_id.name
            else:
                seller.name = _('New Seller')

    @api.depends('state', 'kyc_verified')
    def _compute_can_do_commercial_actions(self):
        """
        Compute whether seller can perform commercial actions.
        Requires BOTH state='approved' AND kyc_verified=True.
        """
        for seller in self:
            seller.can_do_commercial_actions = (
                seller.state == 'approved' and seller.kyc_verified
            )

    @api.depends('kyc_doc', 'kyc_verified', 'kyc_rejection_reason')
    def _compute_kyc_status(self):
        """Compute the KYC verification status"""
        for seller in self:
            if seller.kyc_verified:
                seller.kyc_status = 'verified'
            elif seller.kyc_rejection_reason:
                seller.kyc_status = 'rejected'
            elif seller.kyc_doc:
                seller.kyc_status = 'pending'
            else:
                seller.kyc_status = 'not_submitted'

    @api.depends('state', 'kyc_verified', 'kyc_status')
    def _compute_commercial_status_message(self):
        """Compute a human-readable message about commercial status"""
        for seller in self:
            if seller.can_do_commercial_actions:
                seller.commercial_status_message = _('✓ Active - Can publish products and manage orders')
            elif seller.state == 'suspended':
                seller.commercial_status_message = _('⚠ Account suspended - Contact support')
            elif seller.state == 'rejected':
                seller.commercial_status_message = _('✗ Application rejected')
            elif seller.state != 'approved':
                seller.commercial_status_message = _('⏳ Account pending approval')
            elif not seller.kyc_verified:
                if seller.kyc_status == 'not_submitted':
                    seller.commercial_status_message = _('⚠ Please submit KYC documents')
                elif seller.kyc_status == 'pending':
                    seller.commercial_status_message = _('⏳ KYC verification in progress')
                elif seller.kyc_status == 'rejected':
                    seller.commercial_status_message = _('✗ KYC rejected - Please resubmit')
                else:
                    seller.commercial_status_message = _('⚠ KYC verification required')
            else:
                seller.commercial_status_message = _('⚠ Commercial actions restricted')

    @api.depends('product_ids')
    def _compute_statistics(self):
        """Compute seller statistics"""
        for seller in self:
            # Product count - from One2many relationship
            seller.product_count = len(seller.product_ids)
            
            # Order statistics - orders containing seller's products
            if seller.product_ids:
                product_variant_ids = seller.product_ids.mapped('product_variant_ids').ids
                orders = self.env['sale.order'].sudo().search([
                    ('order_line.product_id', 'in', product_variant_ids),
                    ('state', 'in', ['sale', 'done']),
                ])
                seller.order_count = len(orders)
                
                # Calculate total sales from order lines with seller's products
                order_lines = self.env['sale.order.line'].sudo().search([
                    ('order_id', 'in', orders.ids),
                    ('product_id', 'in', product_variant_ids),
                ])
                seller.total_sales = sum(order_lines.mapped('price_subtotal'))
            else:
                seller.order_count = 0
                seller.total_sales = 0.0

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for seller in self:
            if seller.commission_rate < 0 or seller.commission_rate > 100:
                raise ValidationError(_('Commission rate must be between 0 and 100%'))

    # ==========================================
    # KYC ENFORCEMENT METHODS
    # ==========================================

    def ensure_can_do_commercial_actions(self):
        """
        Ensure seller can perform commercial actions (publish products, manage orders, etc.)
        Raises UserError if seller cannot perform commercial actions.
        """
        self.ensure_one()
        if not self.can_do_commercial_actions:
            if self.state != 'approved':
                raise UserError(_(
                    'Your seller account must be approved before you can perform this action.\n'
                    'Current status: %s'
                ) % dict(self._fields['state'].selection).get(self.state, self.state))
            elif not self.kyc_verified:
                if self.kyc_status == 'not_submitted':
                    raise UserError(_(
                        'KYC verification is required before you can perform this action.\n'
                        'Please upload your KYC documents (ID, business license, etc.) and wait for verification.'
                    ))
                elif self.kyc_status == 'pending':
                    raise UserError(_(
                        'Your KYC documents are being reviewed.\n'
                        'Please wait for verification before performing this action.'
                    ))
                elif self.kyc_status == 'rejected':
                    raise UserError(_(
                        'Your KYC verification was rejected.\n'
                        'Reason: %s\n'
                        'Please upload new documents and resubmit.'
                    ) % (self.kyc_rejection_reason or _('No reason provided')))
                else:
                    raise UserError(_('KYC verification is required before you can perform this action.'))
            else:
                raise UserError(_('You cannot perform this action. Please contact support.'))

    def check_can_publish_products(self):
        """Check if seller can publish products. Returns True/False with message."""
        self.ensure_one()
        if self.can_do_commercial_actions:
            return True, _('You can publish products.')
        
        if self.state != 'approved':
            return False, _('Your account must be approved first.')
        if not self.kyc_verified:
            return False, _('KYC verification required to publish products.')
        return False, _('Commercial actions are restricted.')

    def check_can_manage_orders(self):
        """Check if seller can manage orders. Returns True/False with message."""
        self.ensure_one()
        if self.can_do_commercial_actions:
            return True, _('You can manage orders.')
        
        if self.state != 'approved':
            return False, _('Your account must be approved first.')
        if not self.kyc_verified:
            return False, _('KYC verification required to manage orders.')
        return False, _('Commercial actions are restricted.')

    # ==========================================
    # STATE ACTIONS
    # ==========================================

    def action_submit_for_approval(self):
        """Submit seller profile for approval"""
        self.ensure_one()
        if not self.kyc_doc:
            raise UserError(_('Please upload KYC document before submitting for approval.'))
        self.write({'state': 'pending'})
        self.message_post(body=_('Seller profile submitted for approval.'))

    def action_approve(self):
        """Approve seller"""
        self.ensure_one()
        self.write({
            'state': 'approved',
            'approved_date': fields.Datetime.now(),
            'approved_by': self.env.user.id,
        })
        self.message_post(body=_('Seller approved by %s') % self.env.user.name)
        
        # Send notification email
        template = self.env.ref('smart_ecommerce_extension.email_seller_approved', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_reject(self):
        """Reject seller - opens wizard for reason"""
        self.ensure_one()
        return {
            'name': _('Reject Seller'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.seller.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_seller_id': self.id},
        }

    def action_suspend(self):
        """Suspend seller - opens wizard for reason"""
        self.ensure_one()
        return {
            'name': _('Suspend Seller'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.seller.suspend.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_seller_id': self.id},
        }

    def action_reactivate(self):
        """Reactivate suspended seller"""
        self.ensure_one()
        self.write({
            'state': 'approved',
            'suspension_reason': False,
        })
        self.message_post(body=_('Seller reactivated by %s') % self.env.user.name)

    def action_verify_kyc(self):
        """Mark KYC as verified"""
        self.ensure_one()
        if not self.kyc_doc:
            raise UserError(_('No KYC document uploaded. Cannot verify.'))
        self.write({
            'kyc_verified': True,
            'kyc_verified_date': fields.Date.today(),
            'kyc_verified_by': self.env.user.id,
            'kyc_rejection_reason': False,  # Clear any previous rejection
        })
        self.message_post(body=_('KYC verified by %s') % self.env.user.name)
        
        # Send notification email
        template = self.env.ref('smart_ecommerce_extension.email_kyc_verified', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_reject_kyc(self):
        """Reject KYC - opens wizard for reason"""
        self.ensure_one()
        return {
            'name': _('Reject KYC'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.seller.kyc.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_seller_id': self.id},
        }

    def action_request_kyc_resubmission(self):
        """Request seller to resubmit KYC documents"""
        self.ensure_one()
        self.write({
            'kyc_verified': False,
            'kyc_doc': False,
            'kyc_doc_filename': False,
        })
        self.message_post(body=_('KYC document cleared. Seller needs to resubmit.'))

    # ==========================================
    # VIEW ACTIONS
    # ==========================================

    def action_view_products(self):
        """Open list of seller's products"""
        self.ensure_one()
        return {
            'name': _('Products - %s') % self.company_name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'kanban,list,form',
            'views': [(False, 'kanban'), (False, 'list'), (False, 'form')],
            'domain': [('seller_id', '=', self.id)],
            'context': {
                'default_seller_id': self.id,
                'default_sale_ok': True,
                'default_type': 'consu',
                'default_is_storable': True,
            },
            'target': 'current',
        }

    def action_view_orders(self):
        """Open list of orders containing seller's products"""
        self.ensure_one()
        
        order_ids = []
        if self.product_ids:
            product_variant_ids = self.product_ids.mapped('product_variant_ids').ids
            if product_variant_ids:
                orders = self.env['sale.order'].sudo().search([
                    ('order_line.product_id', 'in', product_variant_ids),
                ])
                order_ids = orders.ids
        
        return {
            'name': _('Orders - %s') % self.company_name,
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', order_ids)],
            'context': {'create': False},
            'target': 'current',
        }

    def action_add_product(self):
        """Quick action to add a new product - requires KYC verification"""
        self.ensure_one()
        # Check if seller can perform commercial actions
        self.ensure_can_do_commercial_actions()
        
        return {
            'name': _('New Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'context': {
                'default_seller_id': self.id,
                'default_sale_ok': True,
                'default_is_published': False,  # Don't auto-publish
                'default_type': 'consu',
                'default_is_storable': True,
            },
            'target': 'current',
        }

    # ==========================================
    # PORTAL METHODS
    # ==========================================

    def get_portal_dashboard_data(self):
        """Get dashboard data for seller portal"""
        self.ensure_one()
        today = fields.Date.today()
        
        # Get orders this month
        first_of_month = today.replace(day=1)
        orders_this_month = self.env['sale.order'].sudo().search_count([
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', first_of_month),
        ])
        
        # Get pending orders
        pending_orders = self.env['sale.order'].sudo().search_count([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'sale'),
        ])
        
        return {
            'seller': self,
            'product_count': self.product_count,
            'total_orders': self.order_count,
            'orders_this_month': orders_this_month,
            'pending_orders': pending_orders,
            'total_sales': self.total_sales,
            'rating': self.rating,
            'state': self.state,
        }

    def get_portal_orders(self, page=1, per_page=20):
        """Get orders for seller portal"""
        self.ensure_one()
        domain = [
            ('partner_id', '=', self.partner_id.id),
        ]
        
        total = self.env['sale.order'].sudo().search_count(domain)
        orders = self.env['sale.order'].sudo().search(
            domain,
            limit=per_page,
            offset=(page - 1) * per_page,
            order='date_order desc'
        )
        
        return {
            'orders': orders,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page,
        }

    def get_portal_payments(self, page=1, per_page=20):
        """Get payment history for seller portal"""
        self.ensure_one()
        # This would integrate with a payout system
        # For now, return order payments
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['sale', 'done']),
        ]
        
        orders = self.env['sale.order'].sudo().search(
            domain,
            limit=per_page,
            offset=(page - 1) * per_page,
            order='date_order desc'
        )
        
        payments = []
        for order in orders:
            payments.append({
                'order_id': order.id,
                'order_ref': order.name,
                'date': order.date_order,
                'amount': order.amount_total,
                'commission': order.amount_total * (self.commission_rate / 100),
                'net_amount': order.amount_total * (1 - self.commission_rate / 100),
                'currency': order.currency_id.name,
                'state': 'paid' if order.state == 'done' else 'pending',
            })
        
        return {
            'payments': payments,
            'page': page,
            'per_page': per_page,
        }


class MarketplaceSellerRejectWizard(models.TransientModel):
    _name = 'marketplace.seller.reject.wizard'
    _description = 'Reject Seller Wizard'

    seller_id = fields.Many2one('marketplace.seller', required=True)
    reason = fields.Text(string='Rejection Reason', required=True)

    def action_reject(self):
        self.ensure_one()
        self.seller_id.write({
            'state': 'rejected',
            'rejection_reason': self.reason,
        })
        self.seller_id.message_post(
            body=_('Seller rejected. Reason: %s') % self.reason
        )
        return {'type': 'ir.actions.act_window_close'}


class MarketplaceSellerSuspendWizard(models.TransientModel):
    _name = 'marketplace.seller.suspend.wizard'
    _description = 'Suspend Seller Wizard'

    seller_id = fields.Many2one('marketplace.seller', required=True)
    reason = fields.Text(string='Suspension Reason', required=True)

    def action_suspend(self):
        self.ensure_one()
        self.seller_id.write({
            'state': 'suspended',
            'suspension_reason': self.reason,
        })
        self.seller_id.message_post(
            body=_('Seller suspended. Reason: %s') % self.reason
        )
        return {'type': 'ir.actions.act_window_close'}


class MarketplaceSellerKYCRejectWizard(models.TransientModel):
    _name = 'marketplace.seller.kyc.reject.wizard'
    _description = 'Reject KYC Wizard'

    seller_id = fields.Many2one('marketplace.seller', required=True)
    reason = fields.Text(string='Rejection Reason', required=True,
                         help='Explain why the KYC documents were rejected and what the seller needs to provide.')

    def action_reject_kyc(self):
        """Reject KYC documents with reason"""
        self.ensure_one()
        self.seller_id.write({
            'kyc_verified': False,
            'kyc_rejection_reason': self.reason,
        })
        self.seller_id.message_post(
            body=_('KYC rejected by %s. Reason: %s') % (self.env.user.name, self.reason)
        )
        
        # Send notification email
        template = self.env.ref('smart_ecommerce_extension.email_kyc_rejected', raise_if_not_found=False)
        if template:
            template.send_mail(self.seller_id.id, force_send=True)
        
        return {'type': 'ir.actions.act_window_close'}

