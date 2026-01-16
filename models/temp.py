from odoo import models, fields, api

class res_partner_customer_provider(models.Model):
    _inherit = 'account.move'

    amount_residual = fields.Monetary(readonly=False)
    amount_residual_signed = fields.Monetary(readonly=False)
    amount_tax = fields.Monetary(readonly=False)
    amount_tax_signed = fields.Monetary(readonly=False)
    amount_total = fields.Monetary(readonly=False)
    amount_total_signed = fields.Monetary(readonly=False)
    amount_untaxed = fields.Monetary(readonly=False)
    amount_untaxed_signed = fields.Monetary(readonly=False)
    amount_total_in_currency_signed = fields.Monetary(readonly=False)
    sii_document_number = fields.Integer(readonly=False)
    invoice_date = fields.Date(readonly=False)
    sii_code = fields.Integer(readonly=False)
    sii_xml_dte = fields.Text(readonly=False)
    invoice_line_ids = fields.One2many(readonly=False)
    line_ids = fields.One2many(readonly=False)
    sequence_number = fields.Integer(readonly=False)