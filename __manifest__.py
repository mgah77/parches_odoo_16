# -*- coding: utf-8 -*-

{
    'name': 'Parches Odoo',
    'version': '1.01',
    'category': 'General',
    'summary': '',
    'description': """
    Parches Odoo

       """,
    'author' : 'M.Gah',
    'website': '',
    'depends': ['base','l10n_cl_fe','contacts'],
    'data': [
            "security/groups.xml",
            "security/ir.model.access.csv",
            "views/partner.xml"
    ],
         
    'installable': True,
    'auto_install': False,
    'application': True,
}
