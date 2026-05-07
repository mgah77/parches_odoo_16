# -*- coding: utf-8 -*-

{
    'name': 'Parches Odoo',
    'version': '1.02',
    'category': 'General',
    'summary': '',
    'description': """
    Parches Odoo

       """,
    'author' : 'M.Gah',
    'website': '',
    'depends': ['base','l10n_cl_fe','contacts','l10n_latam_base','l10n_cl','base_vat','stock','l10n_cl_stock_picking'],
    'data': [
            "security/groups.xml",
            "security/ir.model.access.csv",
            "views/partner.xml",
            "views/sale_order.xml"
    ],
         
    'installable': True,
    'auto_install': False,
    'application': True,
}
