# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ==========================================
    # SELLER ATTRIBUTION
    # ==========================================
    
    # Seller relationship - links product to marketplace seller
    seller_id = fields.Many2one(
        'marketplace.seller',
        string='Seller',
        index=True,
        tracking=True,
        help='The marketplace seller who owns this product',
    )
    
    # Seller KYC status - computed from seller for easy access (not stored to avoid migration issues)
    seller_kyc_verified = fields.Boolean(
        string='Seller KYC Verified',
        related='seller_id.kyc_verified',
        readonly=True,
    )
    seller_can_sell = fields.Boolean(
        string='Seller Can Sell',
        related='seller_id.can_do_commercial_actions',
        readonly=True,
        help='Indicates if the seller is approved and KYC verified',
    )
    
    # ==========================================
    # PRODUCT PUBLICATION WORKFLOW
    # ==========================================
    
    product_state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ], string='Product Status', default='draft', required=True, tracking=True, index=True,
       help='Product publication workflow state')
    
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)
    
    # Approval tracking
    submitted_date = fields.Datetime(string='Submitted Date', readonly=True)
    approved_date = fields.Datetime(string='Approved Date', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    
    # Admin notes for review
    admin_review_notes = fields.Text(
        string='Admin Notes',
        groups='sales_team.group_sale_manager',
        help='Internal notes for admin review',
    )
    
    # Marketplace categories
    marketplace_categ_ids = fields.Many2many(
        'marketplace.category',
        'product_template_marketplace_categ_rel',
        'product_id',
        'category_id',
        string='Marketplace Categories',
        help='Categories specific to the marketplace',
    )
    
    # Featured/highlighted product
    is_featured = fields.Boolean(
        string='Featured Product',
        default=False,
        help='Show in featured products sections',
    )
    featured_start_date = fields.Date(string='Featured Start')
    featured_end_date = fields.Date(string='Featured End')
    
    # Seller SKU (seller's own product code)
    seller_sku = fields.Char(
        string='Seller SKU',
        index=True,
        help="Seller's own product reference code",
    )
    
    # Condition for used/refurbished products
    product_condition = fields.Selection([
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('very_good', 'Very Good'),
        ('good', 'Good'),
        ('acceptable', 'Acceptable'),
        ('refurbished', 'Refurbished'),
    ], string='Condition', default='new')
    
    # Warranty
    warranty_months = fields.Integer(string='Warranty (months)', default=0)
    warranty_description = fields.Text(string='Warranty Details')
    
    # Return policy override
    return_days = fields.Integer(string='Return Period (days)', default=14)
    return_policy = fields.Text(string='Return Policy')
    
    # Stock management per seller
    seller_stock_location_id = fields.Many2one(
        'stock.location',
        string='Seller Stock Location',
        compute='_compute_seller_stock_location',
        store=False,
        help='Stock location for this seller',
    )
    seller_available_qty = fields.Float(
        string='Seller Available Qty',
        compute='_compute_seller_stock',
        digits='Product Unit of Measure',
    )
    
    # Brand and Model fields
    brand = fields.Char(
        string='Brand',
        index=True,
        tracking=True,
        help='Product brand name for filtering and display',
    )
    product_model = fields.Char(
        string='Model',
        tracking=True,
        help='Product model number or name',
    )
    
    # Rich specifications
    specifications = fields.Html(
        string='Specifications',
        sanitize_attributes=False,
        help='Detailed product specifications in HTML format',
    )
    
    # Video support
    video_url = fields.Char(
        string='Video URL',
        help='YouTube, Vimeo, or direct video URL for product demonstration',
    )
    
    # Second image for hover effect
    image_hover = fields.Binary(
        string='Hover Image',
        attachment=True,
        help='Secondary image shown on product card hover',
    )
    
    # Availability - Extend if not already present (check marketplace_core)
    availability_status = fields.Selection([
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
    ], string='Availability Status', compute='_compute_availability_status', store=True)
    
    low_stock_threshold = fields.Integer(
        string='Low Stock Threshold',
        default=10,
        help='Quantity below which product is marked as low stock',
    )
    
    # Delivery estimation
    estimated_delivery_days = fields.Integer(
        string='Estimated Delivery Days',
        default=3,
        help='Default number of days for delivery estimation',
    )
    
    # Shipping weight (if not from marketplace_core)
    shipping_weight_kg = fields.Float(
        string='Shipping Weight (kg)',
        default=0.0,
        help='Product weight in kilograms for shipping calculations',
    )

    @api.depends('qty_available', 'is_storable', 'low_stock_threshold')
    def _compute_availability_status(self):
        """Compute availability status based on stock quantity"""
        for product in self:
            # Only compute availability for storable products (products that track inventory)
            if not product.is_storable:
                product.availability_status = 'in_stock'
                continue
            
            qty = product.qty_available
            threshold = product.low_stock_threshold or 10
            
            if qty <= 0:
                product.availability_status = 'out_of_stock'
            elif qty < threshold:
                product.availability_status = 'low_stock'
            else:
                product.availability_status = 'in_stock'

    def _compute_seller_stock_location(self):
        """Get stock location for the seller"""
        for product in self:
            if product.seller_id and product.seller_id.stock_location_id:
                product.seller_stock_location_id = product.seller_id.stock_location_id
            else:
                product.seller_stock_location_id = False

    def _compute_seller_stock(self):
        """Compute available quantity at seller's stock location"""
        for product in self:
            if product.seller_id and product.seller_id.stock_location_id:
                # Get stock quant for seller's location
                quants = self.env['stock.quant'].search([
                    ('product_id', 'in', product.product_variant_ids.ids),
                    ('location_id', '=', product.seller_id.stock_location_id.id),
                ])
                product.seller_available_qty = sum(quants.mapped('quantity'))
            else:
                product.seller_available_qty = product.qty_available

    # ==========================================
    # PRODUCT WORKFLOW ACTIONS
    # ==========================================

    def action_submit_for_approval(self):
        """Submit product for admin approval"""
        for product in self:
            if product.product_state != 'draft':
                raise UserError(_('Only draft products can be submitted for approval.'))
            
            # Check if seller is assigned for marketplace products
            if product.seller_id and not product.seller_id.can_do_commercial_actions:
                raise UserError(_(
                    'Cannot submit product for approval.\n'
                    'The seller "%(seller)s" must be approved and KYC verified first.'
                ) % {'seller': product.seller_id.company_name})
            
            # Validate required fields
            if not product.name:
                raise UserError(_('Product name is required.'))
            if product.list_price <= 0:
                raise UserError(_('Product price must be greater than 0.'))
            
            product.write({
                'product_state': 'pending',
                'submitted_date': fields.Datetime.now(),
            })
            
            # Notify admins
            product._notify_admin_new_product()
        
        return True

    def action_approve_product(self):
        """Approve product for publication - auto-publishes if seller is approved and KYC verified"""
        for product in self:
            if product.product_state != 'pending':
                raise UserError(_('Only pending products can be approved.'))
            
            vals = {
                'product_state': 'approved',
                'approved_date': fields.Datetime.now(),
                'approved_by': self.env.user.id,
                'rejection_reason': False,
            }
            
            # Auto-publish if seller can do commercial actions (approved + KYC verified)
            if product.seller_id and product.seller_id.can_do_commercial_actions:
                vals['is_published'] = True
                product.message_post(body=_('Product approved and auto-published to website.'))
            else:
                product.message_post(body=_('Product approved. It will be published when seller completes verification.'))
            
            product.write(vals)
            
            # Notify seller
            product._notify_seller_product_approved()
        
        return True

    def action_reject_product(self):
        """Open wizard to reject product with reason"""
        self.ensure_one()
        return {
            'name': _('Reject Product'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_id': self.id},
        }

    def action_set_to_draft(self):
        """Reset product to draft state"""
        for product in self:
            product.write({
                'product_state': 'draft',
                'rejection_reason': False,
            })
        return True

    def action_archive_product(self):
        """Archive the product"""
        for product in self:
            product.write({
                'product_state': 'archived',
                'is_published': False,
                'active': False,
            })
        return True

    def action_unarchive_product(self):
        """Unarchive the product"""
        for product in self:
            product.write({
                'product_state': 'draft',
                'active': True,
            })
        return True

    def _notify_admin_new_product(self):
        """Send notification to admins about new product submission"""
        self.ensure_one()
        template = self.env.ref('smart_ecommerce_extension.email_admin_new_product', raise_if_not_found=False)
        if template:
            # Get sale managers
            managers = self.env['res.users'].search([
                ('groups_id', 'in', self.env.ref('sales_team.group_sale_manager').id)
            ])
            for manager in managers[:3]:  # Limit to 3 managers
                template.send_mail(self.id, email_values={'email_to': manager.email})

    def _notify_seller_product_approved(self):
        """Send notification to seller when product is approved"""
        self.ensure_one()
        if self.seller_id and self.seller_id.user_id:
            template = self.env.ref('smart_ecommerce_extension.email_seller_product_approved', raise_if_not_found=False)
            if template:
                template.send_mail(self.id)

    # ==========================================
    # KYC & WORKFLOW ENFORCEMENT FOR PUBLISHING
    # ==========================================

    @api.constrains('is_published', 'seller_id', 'product_state')
    def _check_publishing_constraints(self):
        """
        Prevent publishing products if:
        1. Seller's KYC is not verified
        2. Product is not approved by admin
        """
        for product in self:
            if product.is_published:
                # Check product approval state
                if product.product_state != 'approved':
                    raise ValidationError(_(
                        'Cannot publish product "%(product)s".\n'
                        'The product must be approved by admin first.\n'
                        'Current status: %(status)s'
                    ) % {
                        'product': product.name,
                        'status': dict(product._fields['product_state'].selection).get(
                            product.product_state, product.product_state
                        ),
                    })
                
                # Check seller KYC
                if product.seller_id:
                    if not product.seller_id.can_do_commercial_actions:
                        if product.seller_id.state != 'approved':
                            raise ValidationError(_(
                                'Cannot publish product "%(product)s".\n'
                                'The seller account "%(seller)s" is not approved yet.\n'
                                'Current status: %(status)s'
                            ) % {
                                'product': product.name,
                                'seller': product.seller_id.company_name,
                                'status': dict(product.seller_id._fields['state'].selection).get(
                                    product.seller_id.state, product.seller_id.state
                                ),
                            })
                        else:
                            raise ValidationError(_(
                                'Cannot publish product "%(product)s".\n'
                                'The seller "%(seller)s" must complete KYC verification first.\n'
                                'Please upload KYC documents and wait for verification.'
                            ) % {
                                'product': product.name,
                                'seller': product.seller_id.company_name,
                            })

    def write(self, vals):
        """Override write to check KYC and product state before publishing"""
        # Skip publishing check if context flag is set (for portal updates)
        if self.env.context.get('skip_publishing_check'):
            return super().write(vals)
        
        # Check if trying to publish
        if vals.get('is_published'):
            for product in self:
                # Check product state
                product_state = vals.get('product_state', product.product_state)
                if product_state != 'approved':
                    raise UserError(_(
                        'Cannot publish product "%(product)s".\n'
                        'The product must be approved by admin first.\n'
                        'Please submit for approval and wait for review.'
                    ) % {'product': product.name})
                
                # Check seller KYC
                if product.seller_id and not product.seller_id.can_do_commercial_actions:
                    raise UserError(_(
                        'Cannot publish product "%(product)s".\n'
                        'The seller "%(seller)s" must be approved and KYC verified first.\n\n'
                        '%(status_message)s'
                    ) % {
                        'product': product.name,
                        'seller': product.seller_id.company_name,
                        'status_message': product.seller_id.commercial_status_message or '',
                    })
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to prevent publishing products without approval"""
        for vals in vals_list:
            # Cannot create and directly publish
            if vals.get('is_published'):
                raise UserError(_(
                    'Cannot create and directly publish a product.\n'
                    'Please create the product first, then submit for admin approval.'
                ))
            
            # Set default product_state
            if 'product_state' not in vals:
                vals['product_state'] = 'draft'
        
        return super().create(vals_list)

    def action_publish(self):
        """Action to publish product - checks approval and KYC first"""
        for product in self:
            if product.product_state != 'approved':
                raise UserError(_(
                    'Cannot publish product "%(product)s".\n'
                    'The product must be approved by admin first.'
                ) % {'product': product.name})
            if product.seller_id:
                product.seller_id.ensure_can_do_commercial_actions()
        return self.write({'is_published': True})

    def action_unpublish(self):
        """Action to unpublish product"""
        return self.write({'is_published': False})

    def action_quick_approve_and_publish(self):
        """Admin action to approve and publish in one step"""
        for product in self:
            if product.seller_id and not product.seller_id.can_do_commercial_actions:
                raise UserError(_(
                    'Cannot publish product. Seller KYC verification is required.'
                ))
            product.write({
                'product_state': 'approved',
                'approved_date': fields.Datetime.now(),
                'approved_by': self.env.user.id,
                'is_published': True,
            })
        return True

    def get_availability_badge_class(self):
        """Return CSS class for availability badge"""
        self.ensure_one()
        mapping = {
            'in_stock': 'badge-success',
            'low_stock': 'badge-warning',
            'out_of_stock': 'badge-danger',
        }
        return mapping.get(self.availability_status, 'badge-secondary')

    def get_availability_label(self):
        """Return human-readable availability label"""
        self.ensure_one()
        labels = {
            'in_stock': _('In Stock'),
            'low_stock': _('Low Stock'),
            'out_of_stock': _('Out of Stock'),
        }
        return labels.get(self.availability_status, _('Unknown'))

    def get_estimated_delivery_date(self, city=None):
        """
        Calculate estimated delivery date based on product and delivery zone.
        
        Args:
            city: Customer city for zone-based estimation
            
        Returns:
            dict with min_date, max_date, and formatted string
        """
        self.ensure_one()
        base_days = self.estimated_delivery_days or 3
        
        # Check for delivery zone override
        if city:
            zone = self.env['delivery.zone'].search([
                ('city_ids', 'ilike', city)
            ], limit=1)
            if zone and zone.estimated_days:
                base_days = zone.estimated_days
        
        # Calculate dates (skip weekends for business days)
        today = fields.Date.today()
        min_date = today + timedelta(days=base_days)
        max_date = today + timedelta(days=base_days + 2)
        
        return {
            'min_date': min_date,
            'max_date': max_date,
            'formatted': _('%(min)s - %(max)s') % {
                'min': min_date.strftime('%b %d'),
                'max': max_date.strftime('%b %d'),
            },
            'days_range': f"{base_days}-{base_days + 2}",
        }

    def get_video_embed_url(self):
        """Convert video URL to embeddable format"""
        self.ensure_one()
        if not self.video_url:
            return False
        
        url = self.video_url.strip()
        
        # YouTube
        if 'youtube.com/watch' in url:
            video_id = url.split('v=')[1].split('&')[0] if 'v=' in url else None
            if video_id:
                return f'https://www.youtube.com/embed/{video_id}'
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
            return f'https://www.youtube.com/embed/{video_id}'
        
        # Vimeo
        if 'vimeo.com/' in url:
            video_id = url.split('vimeo.com/')[1].split('?')[0]
            return f'https://player.vimeo.com/video/{video_id}'
        
        return url  # Return as-is for direct URLs

    @api.model
    def get_brands(self, limit=50):
        """Get list of unique brands for filtering"""
        self.env.cr.execute("""
            SELECT DISTINCT brand
            FROM product_template
            WHERE brand IS NOT NULL 
              AND brand != ''
              AND is_published = true
            ORDER BY brand
            LIMIT %s
        """, (limit,))
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """
        Override search to filter out products from non-approved sellers on website.
        Products without sellers are always visible.
        Products with sellers are only visible if seller is approved and can do commercial actions.
        """
        # Check if this is a website context (has website in context or searching published products)
        if self.env.context.get('website_id') or self.env.context.get('from_website'):
            # Add filter for approved sellers only
            # Allow products without sellers OR products from approved sellers
            approved_seller_filter = [
                '|',
                ('seller_id', '=', False),
                '&',
                ('seller_id.state', '=', 'approved'),
                ('seller_id.can_do_commercial_actions', '=', True),
            ]
            domain = list(domain) + approved_seller_filter
        
        return super()._search(domain, offset=offset, limit=limit, order=order)

    def _is_visible_on_website(self):
        """
        Check if product should be visible on website.
        Extends standard check to also verify seller is approved.
        """
        for product in self:
            # If product has a seller, check seller status
            if product.seller_id:
                if product.seller_id.state != 'approved' or not product.seller_id.can_do_commercial_actions:
                    return False
        return True

