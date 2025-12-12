# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SellerCommission(models.Model):
    """
    SMART Commission System
    Tracks commissions per order/seller with payout management
    """
    _name = 'seller.commission'
    _description = 'Seller Commission'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        default=lambda self: _('New'),
        required=True,
        readonly=True,
    )
    
    seller_id = fields.Many2one(
        'marketplace.seller',
        string='Seller',
        required=True,
        ondelete='restrict',
        index=True,
    )
    order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='cascade',
        index=True,
    )
    
    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        related='seller_id.currency_id',
        store=True,
    )
    order_amount = fields.Monetary(
        string='Order Amount',
        currency_field='currency_id',
        help='Total order amount for seller products',
    )
    commission_rate = fields.Float(
        string='Commission Rate (%)',
        digits=(5, 2),
        help='Commission percentage at time of order',
    )
    commission_amount = fields.Monetary(
        string='Commission Amount',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
    )
    seller_earnings = fields.Monetary(
        string='Seller Earnings',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True,
        help='Amount due to seller (order amount - commission)',
    )
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True, tracking=True)
    
    # Payment tracking
    payout_date = fields.Date(string='Payout Date', readonly=True)
    payout_reference = fields.Char(string='Payout Reference')
    payout_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Payout Method')
    
    # Dates
    order_date = fields.Datetime(
        related='order_id.date_order',
        store=True,
        string='Order Date',
    )
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True)
    
    # Notes
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('seller.commission') or _('New')
        return super().create(vals_list)

    @api.depends('order_amount', 'commission_rate')
    def _compute_amounts(self):
        for record in self:
            record.commission_amount = record.order_amount * (record.commission_rate / 100)
            record.seller_earnings = record.order_amount - record.commission_amount

    def action_confirm(self):
        """Confirm the commission record"""
        self.write({
            'state': 'confirmed',
            'confirmation_date': fields.Datetime.now(),
        })

    def action_mark_paid(self):
        """Mark commission as paid"""
        self.write({
            'state': 'paid',
            'payout_date': fields.Date.today(),
        })

    def action_cancel(self):
        """Cancel the commission record"""
        if self.state == 'paid':
            raise UserError(_('Cannot cancel a paid commission.'))
        self.write({'state': 'cancelled'})

    def action_reset_to_pending(self):
        """Reset to pending state"""
        if self.state == 'paid':
            raise UserError(_('Cannot reset a paid commission.'))
        self.write({'state': 'pending'})


class SellerCommissionPayout(models.Model):
    """
    Batch payout to sellers
    """
    _name = 'seller.commission.payout'
    _description = 'Seller Commission Payout'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Payout Reference',
        default=lambda self: _('New'),
        required=True,
        readonly=True,
    )
    
    seller_id = fields.Many2one(
        'marketplace.seller',
        string='Seller',
        required=True,
        ondelete='restrict',
    )
    
    # Amounts
    currency_id = fields.Many2one(
        'res.currency',
        related='seller_id.currency_id',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Total Payout',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True,
    )
    commission_ids = fields.One2many(
        'seller.commission',
        'payout_reference',
        string='Included Commissions',
        domain="[('state', '=', 'confirmed')]",
    )
    commission_count = fields.Integer(
        string='# Commissions',
        compute='_compute_totals',
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    # Payment details
    payout_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash'),
        ('other', 'Other'),
    ], string='Payment Method', required=True)
    payout_date = fields.Date(string='Payout Date')
    bank_name = fields.Char(related='seller_id.bank_name', readonly=True)
    bank_account = fields.Char(related='seller_id.bank_account', readonly=True)
    
    # Notes
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('seller.commission.payout') or _('New')
        return super().create(vals_list)

    @api.depends('commission_ids', 'commission_ids.seller_earnings')
    def _compute_totals(self):
        for record in self:
            commissions = record.commission_ids.filtered(lambda c: c.state == 'confirmed')
            record.total_amount = sum(commissions.mapped('seller_earnings'))
            record.commission_count = len(commissions)

    def action_confirm(self):
        """Confirm payout"""
        if not self.commission_ids:
            raise UserError(_('No commissions to pay out.'))
        self.write({'state': 'confirmed'})

    def action_mark_paid(self):
        """Mark payout as completed and update all commissions"""
        self.write({
            'state': 'paid',
            'payout_date': fields.Date.today(),
        })
        # Update all included commissions
        self.commission_ids.write({
            'state': 'paid',
            'payout_date': fields.Date.today(),
            'payout_reference': self.name,
            'payout_method': self.payout_method,
        })
        
        # Post message to seller
        self.seller_id.message_post(
            body=_('Payout of %s %s has been processed. Reference: %s') % (
                self.total_amount, self.currency_id.symbol, self.name
            )
        )

    def action_cancel(self):
        """Cancel payout"""
        if self.state == 'paid':
            raise UserError(_('Cannot cancel a completed payout.'))
        # Reset commissions
        self.commission_ids.write({
            'payout_reference': False,
        })
        self.write({'state': 'cancelled'})


class SaleOrderCommissionMixin(models.Model):
    """
    Mixin to add commission computation to sale orders
    """
    _inherit = 'sale.order'

    commission_ids = fields.One2many(
        'seller.commission',
        'order_id',
        string='Commissions',
    )
    total_commission = fields.Monetary(
        string='Total Commission',
        compute='_compute_commission_totals',
        currency_field='currency_id',
    )
    total_seller_earnings = fields.Monetary(
        string='Total Seller Earnings',
        compute='_compute_commission_totals',
        currency_field='currency_id',
    )

    @api.depends('commission_ids', 'commission_ids.commission_amount', 'commission_ids.seller_earnings')
    def _compute_commission_totals(self):
        for order in self:
            order.total_commission = sum(order.commission_ids.mapped('commission_amount'))
            order.total_seller_earnings = sum(order.commission_ids.mapped('seller_earnings'))

    def _create_seller_commissions(self):
        """
        Create commission records for each seller in the order.
        Called when order is confirmed.
        """
        self.ensure_one()
        
        # Group order lines by seller
        seller_amounts = {}
        for line in self.order_line.filtered(lambda l: not l.is_delivery):
            seller = line.product_id.product_tmpl_id.seller_id
            if seller and seller.id:
                if seller.id not in seller_amounts:
                    seller_amounts[seller.id] = {
                        'seller': seller,
                        'amount': 0.0,
                    }
                seller_amounts[seller.id]['amount'] += line.price_subtotal
        
        # Create commission records
        Commission = self.env['seller.commission']
        for seller_id, data in seller_amounts.items():
            seller = data['seller']
            amount = data['amount']
            
            if amount > 0:
                # Check if commission already exists
                existing = Commission.search([
                    ('order_id', '=', self.id),
                    ('seller_id', '=', seller.id),
                ], limit=1)
                
                if not existing:
                    Commission.create({
                        'seller_id': seller.id,
                        'order_id': self.id,
                        'order_amount': amount,
                        'commission_rate': seller.commission_rate,
                        'state': 'pending',
                    })
        
        return True

    def action_confirm(self):
        """Override to create commission records on order confirmation"""
        result = super().action_confirm()
        
        for order in self:
            order._create_seller_commissions()
        
        return result
