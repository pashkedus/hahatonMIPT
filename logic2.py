import datetime
from logic import NestingEngine as BaseEngine

class NestingEngine(BaseEngine):
    def pack(self, orders, inter_cut_map):
        pool_by_priority = {}
        for o in orders:
            p = o['priority']
            if p not in pool_by_priority: pool_by_priority[p] = []
            pool_by_priority[p].append(o)

        priorities = sorted(pool_by_priority.keys())
        bobbins, current_bobbin_items, current_y_in_bobbin = [], [], 0
        alloy, thick = orders[0]['alloy'], orders[0]['thickness']
        gap = inter_cut_map.get((alloy, thick), 5)

        all_items = []
        for p in priorities: all_items.extend(pool_by_priority[p])
        for s in all_items: s['placed'] = False

        for p in priorities:
            main_orders = [o for o in pool_by_priority[p] if not o['placed']]
            main_orders.sort(key=lambda x: x['length'], reverse=True)
            active_sats = [s for s in all_items if not s['placed']]
            active_sats.sort(key=lambda x: x['width'], reverse=True)

            for mo in main_orders:
                if mo['placed']: continue
                if current_y_in_bobbin + mo['length'] > self.max_length:
                    if current_bobbin_items: bobbins.append(current_bobbin_items)
                    current_bobbin_items, current_y_in_bobbin = [], 0
                
                y_start = current_y_in_bobbin
                current_bobbin_items.append({
                    "order_id": mo['id'], "type": "main", "priority": mo['priority'],
                    "coordinates": {"x_start_mm": self.edge_trim, "y_start_m": round(y_start, 3), "width_mm": mo['width'], "length_m": mo['length']}
                })
                mo['placed'] = True
                
                # МЕТОД Б: Заполнение колонками
                rem_w = self.usable_width - mo['width'] - gap
                curr_x = self.edge_trim + mo['width'] + gap
                while rem_w > 0:
                    col_w, stack_y, found = 0, 0, False
                    while stack_y < mo['length']:
                        best_idx = -1
                        for i, s in enumerate(active_sats):
                            if not s['placed'] and s['width'] <= rem_w and (stack_y + s['length']) <= mo['length']:
                                best_idx = i; break
                        if best_idx != -1:
                            s = active_sats.pop(best_idx)
                            current_bobbin_items.append({
                                "order_id": s['id'], "type": "satellite", "priority": s['priority'],
                                "coordinates": {"x_start_mm": curr_x, "y_start_m": round(y_start + stack_y, 3), "width_mm": s['width'], "length_m": s['length']}
                            })
                            s['placed'] = True
                            col_w = max(col_w, s['width'])
                            stack_y += s['length'] + (gap/1000)
                            found = True
                        else: break
                    if found:
                        rem_w -= (col_w + gap); curr_x += (col_w + gap)
                    else: break
                current_y_in_bobbin += mo['length']

        if current_bobbin_items: bobbins.append(current_bobbin_items)
        res = self.finalize(bobbins, alloy, thick, gap)
        res["instruction_metadata"]["batch_id"] = f"RUN-B-{datetime.datetime.now().strftime('%H%M%S')}"
        return res
