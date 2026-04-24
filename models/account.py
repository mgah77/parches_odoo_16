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

    def _compute_amount(self):
        for move in self:
            if move.payment_state == 'invoicing_legacy':
                # invoicing_legacy state is set via SQL when setting setting field
                # invoicing_switch_threshold (defined in account_accountant).
                # The only way of going out of this state is through this setting,
                # so we don't recompute it here.
                move.payment_state = move.payment_state
                continue

            total_untaxed = 0.0
            total_untaxed_currency = 0.0
            total_tax = 0.0
            total_tax_currency = 0.0
            total_to_pay = 0.0
            total_residual = 0.0
            total_residual_currency = 0.0
            total = 0.0
            total_currency = 0.0
            total_retencion = 0
            total_retencion_currency = 0
            sign = move.direction_sign
            for line in move.line_ids:
                if move.is_invoice(True):
                    # === Invoices ===
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                        if line.tax_repartition_line_id.sii_type in ['R', 'A']:
                            total_retencion += line.balance
                            total_retencion_currency += line.amount_currency
                            if line.tax_repartition_line_id.credec:
                                total_tax -= line.balance
                                total_tax_currency -= line.amount_currency
                            total -= (sign * line.balance)
                            total_currency -= (sign * line.amount_currency)
                    elif line.display_type in ('product', 'rounding', 'R', 'D', 'C'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            # ======================================================================
            # INICIO MODIFICACIÓN SOLICITADA
            # ======================================================================
            # Forzamos el signo a -1 si es nota de crédito antes de calcular los totales finales
            if move.move_type == 'out_refund':
                sign = -1
            # (Si también necesitas esto para Notas de Crédito de Compra, agrega: or move.move_type == 'in_refund')
            # ======================================================================

            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency
            move.amount_residual = -sign * total_residual_currency
            move.amount_untaxed_signed = -total_untaxed
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_residual_signed = total_residual
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
            move.amount_tax_retencion = sign * total_retencion_currency
            move.amount_tax_retencion_signed = -total_retencion