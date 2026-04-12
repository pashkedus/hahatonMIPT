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
            mains = sorted([o for o in pool[p] if not o['placed']], key=lambda x: (x['length'], x['width']), reverse=True)
            while mains:
                mo = mains[0]
                if mo['placed']: mains.pop(0); continue
                
                row = [mo]; mo['placed'] = True
                row_w, row_h = mo['width'], mo['length']
                
                # Ищем заказы ТОЙ ЖЕ длины, чтобы идеально закрыть ширину
                for i in range(1, len(mains)):
                    sub = mains[i]
                    if not sub['placed'] and (row_w + gap + sub['width']) <= self.usable_width:
                        if abs(sub['length'] - row_h) < 0.5: # Если длины почти равны
                            row.append(sub); sub['placed'] = True
                            row_w += gap + sub['width']
                
                if current_y + row_h > self.max_length:
                    bobbins.append(current_map); current_map, current_y = [], 0
                
                curr_x = self.edge_trim
                for item in row:
                    current_map.append(self._create_item(item, curr_x, current_y, "main"))
                    curr_x += item['width'] + gap
                
                # Добиваем остаток ширины спутниками
                rem_w = self.usable_width - row_w
                if rem_w > 10:
                    for s in orders:
                        if not s['placed'] and s['width'] <= rem_w and s['length'] <= row_h:
                            current_map.append(self._create_item(s, curr_x, current_y, "satellite"))
                            s['placed'] = True; break

                current_y += row_h
                mains = [o for o in mains if not o['placed']]

        if current_map: bobbins.append(current_map)
        return self.finalize(bobbins, alloy, thick, gap, "C")
