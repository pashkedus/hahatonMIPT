import datetime

class NestingEngine:
    def __init__(self, bobbin_width=1500, bobbin_length=10000, edge_trim=15):
        self.total_width = bobbin_width
        self.max_length = bobbin_length
        self.edge_trim = edge_trim
        self.usable_width = bobbin_width - 2 * edge_trim
        
    def _create_item(self, order, x, y, type_label):
        return {
            "order_id": order['id'], "type": type_label, "priority": order['priority'],
            "w": order['width'], "h": order['length'],
            "coordinates": {"x_start_mm": x, "y_start_m": round(y, 3), "width_mm": order['width'], "length_m": order['length']}
        }

    def finalize(self, bobbins, alloy, thick, gap, method_id):
        total_useful_area = sum(sum(i['w'] * i['h'] for i in b) for b in bobbins) / 1000
        total_length_used = sum(max((i['coordinates']['y_start_m'] + i['coordinates']['length_m']) for i in b) if b else 0 for b in bobbins)
        total_unrolled_area = (total_length_used * self.total_width) / 1000
        waste_area = total_unrolled_area - total_useful_area
        waste_percent = (waste_area / total_unrolled_area * 100) if total_unrolled_area > 0 else 0
        
        return {
            "instruction_metadata": {"batch_id": f"RUN-{method_id}-{datetime.datetime.now().strftime('%H%M%S')}", "factory": "САЗ"},
            "source_material": {"alloy": alloy, "thickness_um": thick, "bobbin_width_mm": self.total_width, "bobbin_length_m": self.max_length},
            "layout_configuration": {"inter_cut_mm": gap, "edge_trim_mm": self.edge_trim},
            "bobbins": bobbins,
            "efficiency_metrics": {"total_used_area_m2": round(total_useful_area, 2), "waste_area_m2": round(waste_area, 2), "waste_percentage": round(waste_percent, 2)}
        }

    def pack(self, orders, inter_cut_map):
        pool = {p: [o for o in orders if o['priority'] == p] for p in set(o['priority'] for o in orders)}
        priorities = sorted(pool.keys())
        for o in orders: o['placed'] = False
        bobbins, current_map, current_y = [], [], 0
        alloy, thick = orders[0]['alloy'], orders[0]['thickness']
        gap = inter_cut_map.get((alloy, thick), 5)

        for p in priorities:
            mains = sorted([o for o in pool[p] if not o['placed']], key=lambda x: x['length'], reverse=True)
            for mo in mains:
                if mo['placed']: continue
                if current_y + mo['length'] > self.max_length:
                    bobbins.append(current_map); current_map, current_y = [], 0
                current_map.append(self._create_item(mo, self.edge_trim, current_y, "main"))
                mo['placed'] = True
                rem_w = self.usable_width - mo['width'] - gap
                curr_x = self.edge_trim + mo['width'] + gap
                for sat in orders:
                    if not sat['placed'] and sat['width'] <= rem_w and sat['length'] <= mo['length']:
                        current_map.append(self._create_item(sat, curr_x, current_y, "satellite"))
                        sat['placed'] = True; break
                current_y += mo['length']
        if current_map: bobbins.append(current_map)
        return self.finalize(bobbins, alloy, thick, gap, "A")
