from odoo import api, fields, models
from odoo.exceptions import except_orm, UserError
from datetime import date, timedelta

class Picking(models.Model):
    _inherit = 'stock.picking'