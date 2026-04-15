import datetime

class NestingEngine:
    def __init__(self, bobbin_width=1500, bobbin_length=10000, edge_trim=15):
        self.total_width = bobbin_width
        self.max_length = bobbin_length
        self.edge_trim = edge_trim
        self.usable_width = bobbin_width - 2 * edge_trim

    def pack(self, orders, gap):
        # Группировка внутри материала по приоритету
        pool = {p: [o for o in orders if o['priority'] == p] for p in set(o['priority'] for o in orders)}
        priorities = sorted(pool.keys())
        for o in orders: o['placed'] = False

        bobbins, current_map, current_y = [], [], 0

        for p in priorities:
            # Сортируем: сначала длинные, потом широкие
            mains = sorted([o for o in pool[p] if not o['placed']], key=lambda x: (x['length'], x['width']), reverse=True)
            
            while mains:
                mo = mains[0]
                if mo['placed']: mains.pop(0); continue
                
                self._check_rotation(mo)
                row_items = [mo]; mo['placed'] = True
                row_w, row_h = mo['width'], mo['length']
                
                # Ищем партнеров из основной очереди в этот же ряд
                for i in range(1, len(mains)):
                    sub = mains[i]
                    if not sub['placed']:
                        self._check_rotation(sub)
                        if (row_w + gap + sub['width']) <= self.usable_width:
                            # Допуск по длине для минимизации ступенчатых отходов
                            if sub['length'] >= row_h * 0.7:
                                row_items.append(sub)
                                sub['placed'] = True
                                row_w += gap + sub['width']
                                row_h = max(row_h, sub['length'])
                
                if current_y + row_h > self.max_length:
                    bobbins.append(current_map); current_map, current_y = [], 0
                
                # Размещаем основные фигуры
                cx = self.edge_trim
                for item in row_items:
                    current_map.append(self._create_item(item, cx, current_y))
                    cx += item['width'] + gap
                
                # Заполнение оставшегося "окна" справа спутниками (Cross-Filling)
                rem_w = self.usable_width - row_w
                if rem_w > 5:
                    self._fill_residual(current_map, orders, cx, current_y, rem_w, row_h, gap)
                
                current_y += row_h
                mains = [o for o in mains if not o['placed']]

        if current_map: bobbins.append(current_map)
        return self._finalize(bobbins, gap)

    def _fill_residual(self, cmap, all_o, x, y, rw, rh, gap):
        """Заполнение пустоты колонками спутников"""
        curr_x = x
        while rw > 5:
            col_w, stack_y, found_col = 0, 0, False
            while stack_y < rh:
                rem_h = rh - stack_y
                candidates = [s for s in all_o if not s['placed'] and s['width'] <= (rw - gap) and s['length'] <= rem_h]
                if not candidates: break
                candidates.sort(key=lambda x: x['length'], reverse=True)
                best_s = candidates[0]
                cmap.append(self._create_item(best_s, curr_x, y + stack_y))
                best_s['placed'] = True
                col_w = max(col_w, best_s['width'])
                stack_y += best_s['length'] + (gap/1000)
                found_col = True
            if found_col:
                rw -= (col_w + gap); curr_x += (col_w + gap)
            else: break

    def _check_rotation(self, o):
        # Вращаем если это экономит длину и не выходит за 1500мм
        if o['length'] * 1000 <= self.usable_width and (o['length'] < o['width']/1000):
            o['width'], o['length'] = o['length'] * 1000, o['width'] / 1000
            o['rotated'] = True
        else: o['rotated'] = False

    def _create_item(self, o, x, y):
        return {
            "id": o['id'], "p": o['priority'], "rotated": o.get('rotated', False),
            "w_mm": round(o['width'], 1), "h_mm": round(o['length'] * 1000, 1),
            "y": round(y, 3), "x": round(x, 1), "h_m": round(o['length'], 3)
        }

    def _finalize(self, bobbins, gap):
        useful = sum(sum(i['w_mm'] * i['h_m'] for i in b) for b in bobbins) / 1000
        total_l = sum(max((i['y'] + i['h_m']) for i in b) if b else 0 for b in bobbins)
        total_a = (total_l * 1500) / 1000
        return {"bobbins": bobbins, "config": {"gap": gap}, "metrics": {"useful_m2": useful, "waste_m2": total_a - useful, "total_len": total_l}}
