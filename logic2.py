import datetime
from logic import NestingEngine as BaseEngine

class NestingEngine(BaseEngine):
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
                
                y_start = current_y
                current_map.append(self._create_item(mo, self.edge_trim, y_start, "main"))
                mo['placed'] = True
                
                rem_w = self.usable_width - mo['width'] - gap
                curr_x = self.edge_trim + mo['width'] + gap
                
                # Набиваем колонку спутниками
                stack_y = 0
                while stack_y < mo['length']:
                    best_s = None
                    for s in orders:
                        if not s['placed'] and s['width'] <= rem_w and (stack_y + s['length']) <= mo['length']:
                            best_s = s; break
                    if best_s:
                        current_map.append(self._create_item(best_s, curr_x, y_start + stack_y, "satellite"))
                        best_s['placed'] = True
                        stack_y += best_s['length'] + (gap/1000)
                    else: break
                
                current_y += mo['length']

        if current_map: bobbins.append(current_map)
        return self.finalize(bobbins, alloy, thick, gap, "B")
