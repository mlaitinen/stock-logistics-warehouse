from odoo import _, api, fields, models
from odoo.tools import groupby


class StockQuant(models.Model):
    _inherit = "stock.quant"

    to_do = fields.Boolean(default=False)

    stock_inventory_ids = fields.Many2many(
        "stock.inventory",
        "stock_inventory_stock_quant_rel",
        string="Stock Inventories",
        copy=False,
    )
    current_inventory_id = fields.Many2one(
        "stock.inventory",
        string="Current Inventory",
        store=True,
    )

    def _apply_inventory(self):
        res = super()._apply_inventory()
        record_moves = self.env["stock.move.line"]
        adjustment = self.env["stock.inventory"].browse()

        for adjustment, quant_list in groupby(
            self, key=lambda x: x.current_inventory_id
        ):
            new_moves = self.env["stock.move.line"]
            for quant in quant_list:
                moves = record_moves.search(
                    [
                        ("product_id", "=", quant.product_id.id),
                        ("lot_id", "=", quant.lot_id.id),
                        "|",
                        ("location_id", "=", quant.location_id.id),
                        ("location_dest_id", "=", quant.location_id.id),
                    ],
                    order="create_date asc",
                ).filtered(
                    lambda x, quant=quant: not x.company_id.id
                    or not quant.company_id.id
                    or quant.company_id.id == x.company_id.id
                )
                if len(moves) == 0:
                    raise ValueError(_("No move lines have been created"))
                move = moves[len(moves) - 1]
                reference = move.reference
                if adjustment.name and move.reference:
                    reference = adjustment.name + ": " + move.reference
                elif adjustment.name:
                    reference = adjustment.name
                move.write(
                    {
                        "inventory_adjustment_id": adjustment.id,
                        "reference": reference,
                    }
                )
                quant.to_do = False
                quant.current_inventory_id = False
                new_moves |= move
            adjustment.stock_move_ids |= new_moves
        if adjustment and self.env.company.stock_inventory_auto_complete:
            adjustment.action_auto_state_to_done()
        return res

    def _get_inventory_fields_write(self):
        return super()._get_inventory_fields_write() + ["to_do"]

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if self.env.context.get(
            "active_model", False
        ) == "stock.inventory" and self.env.context.get("active_id", False):
            self.env["stock.inventory"].browse(
                self.env.context.get("active_id")
            ).refresh_stock_quant_ids()
        return res
