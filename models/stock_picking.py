from odoo import api, fields, models
from odoo.exceptions import except_orm, UserError
from datetime import date, timedelta

class Picking(models.Model):
    _inherit = 'stock.picking'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Verificamos si tiene origen (Sale Order) y un tipo de operación asignado
            if vals.get('origin') and vals.get('picking_type_id'):
                picking_type = self.env['stock.picking.type'].browse(vals['picking_type_id'])
                
                # Nos aseguramos de que sea una entrega de salida (OUT)
                if picking_type.code == 'outgoing':
                    origin = vals.get('origin')
                    
                    so_number = origin.replace('S', '')
                    
                    # Obtener el código del almacén (Ej: 'WH') o usar 'WH' por defecto
                    wh_code = picking_type.warehouse_id.code or 'WH'
                    
                    # Construir el nuevo nombre: WH/OUT/0000
                    new_name = f"{wh_code}/OUT/{so_number}"
                    
                    # Asignar el nombre personalizado. 
                    # Al hacerlo, Odoo no usará la secuencia automática.
                    vals['name'] = new_name

        # Llamamos al create original sin la lógica de secuencia dinámica que causaba el error
        return super().create(vals_list)
