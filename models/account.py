from odoo import models, fields, api ,_
from odoo.tools import frozendict
from contextlib import ExitStack

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
            
            # INICIO: Condición final para forzar signo negativo en out_refund si es > 0
            if move.move_type == 'out_refund':
                if move.amount_total_signed > 0:
                    move.amount_total_signed = -move.amount_total_signed
                if move.amount_total_in_currency_signed > 0:
                    move.amount_total_in_currency_signed = -move.amount_total_in_currency_signed
                  
                # 2. Forzar positivos en los campos estándar (asegurar valor absoluto)
                move.amount_untaxed = abs(move.amount_untaxed)
                move.amount_tax = abs(move.amount_tax)
                move.amount_total = abs(move.amount_total)
                move.amount_residual = abs(move.amount_residual)
                
            # FIN


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'


    def write(self, vals):
        if not vals:
            return True

        protected_fields = self._get_lock_date_protected_fields()
        account_to_write = self.env['account.account'].browse(vals['account_id']) if 'account_id' in vals else None

        if account_to_write and account_to_write.deprecated:
            raise UserError(_('You cannot use a deprecated account.'))

        inalterable_fields = set(self._get_integrity_hash_fields()).union({'inalterable_hash', 'secure_sequence_number'})
        hashed_moves = self.move_id.filtered('inalterable_hash')
        violated_fields = set(vals) & inalterable_fields
        if hashed_moves and violated_fields:
            raise UserError(_(
                "You cannot edit the following fields: %s.\n"
                "The following entries are already hashed:\n%s",
                ', '.join(f['string'] for f in self.fields_get(violated_fields).values()),
                '\n'.join(hashed_moves.mapped('name')),
            ))

        line_to_write = self
        vals = self._sanitize_vals(vals)

        for line in self:
            if not any(self.env['account.move']._field_will_change(line, vals, field_name) for field_name in vals):
                line_to_write -= line
                continue

            if line.parent_state == 'posted' and any(self.env['account.move']._field_will_change(line, vals, field_name) for field_name in ('tax_ids', 'tax_line_id')):
                raise UserError(_('You cannot modify the taxes related to a posted journal item, you should reset the journal entry to draft to do so.'))

            if line.parent_state == 'posted' and any(self.env['account.move']._field_will_change(line, vals, field_name) for field_name in protected_fields['fiscal']):
                line.move_id._check_fiscalyear_lock_date()

            if line.parent_state == 'posted' and any(self.env['account.move']._field_will_change(line, vals, field_name) for field_name in protected_fields['tax']):
                line._check_tax_lock_date()

            if any(self.env['account.move']._field_will_change(line, vals, field_name) for field_name in protected_fields['reconciliation']):
                line._check_reconciliation()

        move_container = {'records': self.move_id}

        with self.move_id._check_balanced(move_container),\
            self.env.protecting(self.env['account.move']._get_protected_vals(vals, self)),\
            self.move_id._sync_dynamic_lines(move_container),\
            self._sync_invoice({'records': self}):

            self = line_to_write
            if not self:
                return True

            # ===== AQUI VA EL AJUSTE =====
            for line in self:
                display_type = vals.get('display_type', line.display_type)
                amount = vals.get('amount_currency', line.amount_currency)

                if (
                    display_type == 'payment_term'
                    and line.move_id.move_type == 'out_refund'
                    and amount
                    and amount > 0
                ):
                    # Ajusta ambos para no desbalancear
                    vals['amount_currency'] = -amount
                    if 'balance' in vals:
                        vals['balance'] = -vals['balance']
            # ============================

            if not self.env.context.get('tracking_disable', False):
                tracking_fields = []
                for value in vals:
                    field = self._fields[value]
                    if hasattr(field, 'related') and field.related:
                        continue
                    if hasattr(field, 'tracking') and field.tracking:
                        tracking_fields.append(value)
                ref_fields = self.env['account.move.line'].fields_get(tracking_fields)

                move_initial_values = {}
                for line in self.filtered(lambda l: l.move_id.posted_before):
                    for field in tracking_fields:
                        if line.move_id.id not in move_initial_values:
                            move_initial_values[line.move_id.id] = {}
                        move_initial_values[line.move_id.id].update({field: line[field]})

            result = super().write(vals)
            self.move_id._synchronize_business_models(['line_ids'])

            if any(field in vals for field in ['account_id', 'currency_id']):
                self._check_constrains_account_id_journal_id()

            if not self.env.context.get('tracking_disable', False):
                for move_id, modified_lines in move_initial_values.items():
                    for line in self.filtered(lambda l: l.move_id.id == move_id):
                        tracking_value_ids = line._mail_track(ref_fields, modified_lines)[1]
                        if tracking_value_ids:
                            msg = _(
                                "Journal Item %s updated",
                                line._get_html_link(title=f"#{line.id}")
                            )
                            line.move_id._message_log(
                                body=msg,
                                tracking_value_ids=tracking_value_ids
                            )

        return result


    @api.model_create_multi
    def create(self, vals_list):

        # ===== AQUI VA EL AJUSTE =====
        for vals in vals_list:
            if vals.get('display_type') == 'payment_term' and vals.get('move_id'):
                move = self.env['account.move'].browse(vals['move_id'])
                if move.move_type == 'out_refund':
                    amount = vals.get('amount_currency')
                    if amount and amount > 0:
                        vals['amount_currency'] = -amount
                        if 'balance' in vals:
                            vals['balance'] = -vals['balance']
        # ============================

        moves = self.env['account.move'].browse({vals['move_id'] for vals in vals_list})
        container = {'records': self}
        move_container = {'records': moves}

        with moves._check_balanced(move_container),\
             ExitStack() as exit_stack,\
             moves._sync_dynamic_lines(move_container),\
             self._sync_invoice(container):

            lines = super().create([self._sanitize_vals(vals) for vals in vals_list])

            exit_stack.enter_context(
                self.env.protecting([
                    protected
                    for vals, line in zip(vals_list, lines)
                    for protected in self.env['account.move']._get_protected_vals(vals, line)
                ])
            )

            container['records'] = lines

        for line in lines:
            if line.move_id.state == 'posted':
                line._check_tax_lock_date()

        lines.move_id._synchronize_business_models(['line_ids'])
        lines._check_constrains_account_id_journal_id()

        return lines