# -*- coding: utf-8 -*-
# Part of SMART eCommerce Extension. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MarketplaceCategory(models.Model):
    """
    Global Marketplace Categories
    Separate from website categories for marketplace-specific organization
    """
    _name = 'marketplace.category'
    _description = 'Marketplace Category'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'sequence, complete_name'

    name = fields.Char(string='Name', required=True, index=True, translate=True)
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        store=True,
        recursive=True,
    )
    
    parent_id = fields.Many2one(
        'marketplace.category',
        string='Parent Category',
        index=True,
        ondelete='cascade',
    )
    parent_path = fields.Char(index=True, unaccent=False)
    
    child_ids = fields.One2many(
        'marketplace.category',
        'parent_id',
        string='Child Categories',
    )
    
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Description and display
    description = fields.Text(string='Description', translate=True)
    image = fields.Binary(string='Image', attachment=True)
    icon = fields.Char(string='Icon Class', help='Font Awesome icon class (e.g., fa-laptop)')
    color = fields.Integer(string='Color Index')
    
    # SEO
    slug = fields.Char(string='URL Slug', index=True)
    meta_title = fields.Char(string='Meta Title', translate=True)
    meta_description = fields.Text(string='Meta Description', translate=True)
    
    # Display settings
    active = fields.Boolean(default=True)
    is_featured = fields.Boolean(string='Featured Category', default=False)
    show_on_homepage = fields.Boolean(string='Show on Homepage', default=False)
    
    # Commission rate override for category
    commission_rate = fields.Float(
        string='Commission Rate (%)',
        default=0.0,
        help='Category-specific commission rate. If 0, seller default is used.',
    )
    
    # Product count
    product_count = fields.Integer(
        string='Products',
        compute='_compute_product_count',
    )
    
    # Website category mapping
    website_categ_ids = fields.Many2many(
        'product.public.category',
        'marketplace_categ_website_categ_rel',
        'marketplace_categ_id',
        'website_categ_id',
        string='Website Categories',
        help='Map to website public categories',
    )
    
    _sql_constraints = [
        ('slug_unique', 'UNIQUE(slug)', 'URL Slug must be unique!'),
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = f'{category.parent_id.complete_name} / {category.name}'
            else:
                category.complete_name = category.name

    def _compute_product_count(self):
        for category in self:
            category.product_count = self.env['product.template'].search_count([
                ('marketplace_categ_ids', 'in', category.id),
                ('is_published', '=', True),
            ])

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive categories.'))

    @api.model
    def create(self, vals):
        # Auto-generate slug if not provided
        if not vals.get('slug') and vals.get('name'):
            vals['slug'] = self._generate_slug(vals['name'])
        return super().create(vals)

    def write(self, vals):
        # Auto-generate slug if name changes and slug is not explicitly set
        if vals.get('name') and 'slug' not in vals:
            for record in self:
                if not record.slug:
                    vals['slug'] = self._generate_slug(vals['name'])
        return super().write(vals)

    def _generate_slug(self, name):
        """Generate URL-friendly slug from name"""
        import re
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while self.search_count([('slug', '=', slug)]):
            slug = f'{base_slug}-{counter}'
            counter += 1
        
        return slug

    def name_get(self):
        return [(category.id, category.complete_name) for category in self]

    @api.model
    def get_featured_categories(self, limit=8):
        """Get featured categories for homepage display"""
        return self.search([
            ('is_featured', '=', True),
            ('active', '=', True),
        ], limit=limit, order='sequence')

    @api.model
    def get_homepage_categories(self, limit=12):
        """Get categories to show on homepage"""
        return self.search([
            ('show_on_homepage', '=', True),
            ('active', '=', True),
            ('parent_id', '=', False),  # Only top-level
        ], limit=limit, order='sequence')

    def get_products(self, limit=None, offset=0):
        """Get published products in this category"""
        domain = [
            ('marketplace_categ_ids', 'in', self.id),
            ('is_published', '=', True),
            ('product_state', '=', 'approved'),
        ]
        return self.env['product.template'].search(domain, limit=limit, offset=offset)

    def action_view_products(self):
        """View products in this category"""
        self.ensure_one()
        return {
            'name': _('Products - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'kanban,list,form',
            'domain': [('marketplace_categ_ids', 'in', self.id)],
            'context': {},
        }


class ProductRejectWizard(models.TransientModel):
    """Wizard to reject a product with reason"""
    _name = 'product.reject.wizard'
    _description = 'Product Rejection Wizard'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='Explain why this product is being rejected',
    )

    def action_reject(self):
        """Reject the product with the given reason"""
        self.ensure_one()
        self.product_id.write({
            'product_state': 'rejected',
            'rejection_reason': self.rejection_reason,
            'is_published': False,
        })
        
        # Notify seller
        if self.product_id.seller_id and self.product_id.seller_id.user_id:
            template = self.env.ref(
                'smart_ecommerce_extension.email_seller_product_rejected',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(self.product_id.id)
        
        return {'type': 'ir.actions.act_window_close'}
