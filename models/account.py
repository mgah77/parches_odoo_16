from odoo import models, fields, api ,_
from odoo.tools import frozendict

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    serie_cheque = fields.Char(string="Serie del cheque")
    banco_cheque_id = fields.Many2one('res.bank', string="Banco del cheque")
    fecha_cobro = fields.Date(string="Fecha de cobro del cheque")
 
class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    serie_cheque = fields.Char(string="Serie del cheque")
    banco_cheque_id = fields.Many2one('res.bank', string="Banco del cheque")
    fecha_cobro = fields.Date(string="Fecha de cobro del cheque")

    def _create_payments(self):
        """Crea los pagos y les pasa los datos del cheque."""
        payments = super()._create_payments()
        for wiz in self:
            payments.write({
                'serie_cheque': wiz.serie_cheque,
                'banco_cheque_id': wiz.banco_cheque_id.id if wiz.banco_cheque_id else False,
                'fecha_cobro': wiz.fecha_cobro,
            })
        return payments

class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def unlink(self):
            moves = (self.debit_move_id.move_id | self.credit_move_id.move_id)
            res = super().unlink()

            # Fuerza el estado "not_paid" en todas las facturas o notas asociadas
            for move in moves:
                if move.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                    move.payment_state = 'not_paid'

            return res

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def get_outbound_types(self, include_receipts=True):
        # Odoo 16 original no tiene 'out_refund' aquí.
        # Al quitarlo, is_inbound() será True para la NC, el signo será -1, 
        # y el cliente irá al Crédito.
        return ['in_invoice'] + (include_receipts and ['in_receipt'] or [])


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    @api.depends('tax_ids', 'currency_id', 'partner_id', 'analytic_distribution', 'balance', 'partner_id', 'move_id.partner_id', 'price_unit')
    def _compute_all_tax(self):
        for line in self:
            sign = line.move_id.direction_sign
            if line.display_type == 'product' and line.move_id.is_invoice(True):
                amount_currency = sign * line.price_unit
                amount = sign * line.price_unit / line.currency_rate
                handle_price_include = True
                quantity = line.quantity
            else:
                amount_currency = line.amount_currency
                amount = line.balance
                handle_price_include = False
                quantity = 1
            compute_all_currency = line.tax_ids.compute_all(
                amount_currency,
                currency=line.currency_id,
                quantity=quantity,
                product=line.product_id,
                partner=line.move_id.partner_id or line.partner_id,
                is_refund=line.is_refund,
                discount=line.discount,
                handle_price_include=handle_price_include,
                include_caba_tags=line.move_id.always_tax_exigible,
                fixed_multiplicator=sign,
            )
            rate = line.amount_currency / line.balance if line.balance else 1
            line.compute_all_tax_dirty = True
            compute_all_tax = {}
            for tax in compute_all_currency['taxes']:
                if tax['amount']:
                    rpl = self.env['account.tax.repartition.line'].sudo().browse(tax['tax_repartition_line_id'])
                    
                    # --- INICIO CORRECCIÓN ---
                    # Calculamos el balance base
                    balance_raw = tax['amount'] / rate
                    
                    # Si es Nota de Crédito de Cliente y el balance es negativo, lo invertimos
                    # El IVA en una NC debe ser Débito (Positivo)
                    if line.move_id.move_type == 'out_refund' and balance_raw < 0:
                        balance_final = -balance_raw
                    else:
                        balance_final = balance_raw
                    # --- FIN CORRECCIÓN ---

                    compute_all_tax[frozendict({
                        'tax_repartition_line_id': tax['tax_repartition_line_id'],
                        'group_tax_id': tax['group'] and tax['group'].id or False,
                        'account_id': tax['account_id'] or line.account_id.id,
                        'currency_id': line.currency_id.id,
                        'analytic_distribution': (tax['analytic'] or not tax['use_in_tax_closing']) and line.analytic_distribution,
                        'tax_ids': [(6, 0, tax['tax_ids'])],
                        'tax_tag_ids': [(6, 0, tax['tag_ids'])],
                        'partner_id': line.move_id.partner_id.id or line.partner_id.id,
                        'move_id': line.move_id.id,
                    })] = {
                        'name': tax['name'],
                        'balance': balance_final, # Usamos la variable corregida
                        'amount_currency': tax['amount'],
                        'tax_base_amount': tax['base'] / rate * (-1 if line.tax_tag_invert else 1),
                    }

            line.compute_all_tax = compute_all_tax
            if not line.tax_repartition_line_id:
                line.compute_all_tax[frozendict({'id': line.id})] = {
                    'tax_tag_ids': [(6, 0, compute_all_currency['base_tags'])],
                }