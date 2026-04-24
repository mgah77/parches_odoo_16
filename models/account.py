from odoo import models, fields, api ,_

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