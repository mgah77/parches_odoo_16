from odoo import models, fields, api ,_
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)



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