import datetime

class NestingEngine:
    def __init__(self, bobbin_width=1500, bobbin_length=10000, edge_trim=15):
        self.total_width = bobbin_width
        self.max_length = bobbin_length
        self.edge_trim = edge_trim
        self.usable_width = bobbin_width - 2 * edge_trim
        
    def pack(self, orders, inter_cut_map):
        pool_by_priority = {}
        for o in orders:
            p = o['priority']
            if p not in pool_by_priority: pool_by_priority[p] = []
            pool_by_priority[p].append(o)

        priorities = sorted(pool_by_priority.keys())
        bobbins = []
        current_bobbin_items = []
        current_y_in_bobbin = 0
        
        alloy = orders[0]['alloy']
        thick = orders[0]['thickness']
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
                
                rem_w = self.usable_width - mo['width'] - gap
                curr_x = self.edge_trim + mo['width'] + gap
                
                idx = 0
                while idx < len(active_sats) and rem_w > 0:
                    sat = active_sats[idx]
                    if not sat['placed'] and sat['width'] <= rem_w and sat['length'] <= mo['length']:
                        current_bobbin_items.append({
                            "order_id": sat['id'], "type": "satellite", "priority": sat['priority'],
                            "coordinates": {"x_start_mm": curr_x, "y_start_m": round(y_start, 3), "width_mm": sat['width'], "length_m": sat['length']}
                        })
                        sat['placed'] = True
                        curr_x += sat['width'] + gap
                        rem_w -= (sat['width'] + gap)
                        active_sats.pop(idx)
                    else: idx += 1
                current_y_in_bobbin += mo['length']

        if current_bobbin_items: bobbins.append(current_bobbin_items)
        return self.finalize(bobbins, alloy, thick, gap)

    def finalize(self, bobbins, alloy, thick, gap):
        total_useful = sum(sum(i['coordinates']['width_mm'] * i['coordinates']['length_m'] for i in b) for b in bobbins) / 1000
        total_area = len(bobbins) * self.total_width * self.max_length / 1000
        waste = total_area - total_useful
        return {
            "instruction_metadata": {"batch_id": f"RUN-A-{datetime.datetime.now().strftime('%H%M%S')}", "timestamp": datetime.datetime.now().isoformat(), "factory": "САЗ", "machine_id": "MILL-05"},
            "source_material": {"alloy": alloy, "thickness_um": thick, "bobbin_width_mm": self.total_width, "bobbin_length_m": self.max_length},
            "layout_configuration": {"inter_cut_mm": gap, "edge_trim_mm": self.edge_trim},
            "bobbins": bobbins,
            "efficiency_metrics": {"total_used_area_m2": round(total_useful, 2), "waste_area_m2": round(waste, 2), "waste_percentage": round((waste/total_area*100), 2)}
        }
