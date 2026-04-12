import datetime

class NestingEngine:
    def __init__(self, bobbin_width=1500, bobbin_length=10000, edge_trim=15):
        self.total_width = bobbin_width
        self.max_length = bobbin_length
        self.edge_trim = edge_trim
        self.usable_width = bobbin_width - 2 * edge_trim

    def pack(self, orders, gap):
        # Разделяем по приоритетам
        pool = {p: [o for o in orders if o['priority'] == p] for p in set(o['priority'] for o in orders)}
        priorities = sorted(pool.keys())
        for o in orders: o['placed'] = False

        bobbins, current_map, current_y = [], [], 0

        for p in priorities:
            # Сортируем: сначала длинные, потом широкие
            mains = sorted([o for o in pool[p] if not o['placed']], key=lambda x: x['length'], reverse=True)
            
            while mains:
                mo = mains[0]
                if mo['placed']: mains.pop(0); continue
                
                self._check_rotation(mo)
                row_items = [mo]; mo['placed'] = True
                row_w = mo['width']
                row_h = mo['length']
                
                # Ищем партнеров ТОГО ЖЕ приоритета с похожей длиной (допуск 20%)
                for i in range(1, len(mains)):
                    sub = mains[i]
                    if not sub['placed']:
                        self._check_rotation(sub)
                        # Проверяем, влезет ли по ширине и не слишком ли короткий (чтобы не плодить обрез по высоте)
                        if (row_w + gap + sub['width']) <= self.usable_width:
                            if sub['length'] >= row_h * 0.8: 
                                row_items.append(sub)
                                sub['placed'] = True
                                row_w += gap + sub['width']
                
                # Смена бобины
                if current_y + row_h > self.max_length:
                    bobbins.append(current_map); current_map, current_y = [], 0
                
                # Размещаем основные
                cx = self.edge_trim
                for item in row_items:
                    current_map.append(self._create_item(item, cx, current_y))
                    cx += item['width'] + gap
                
                # ЗАПОЛНЕНИЕ ПУСТОТ (ВЕРТИКАЛЬНЫЙ СТЕК)
                # Ищем спутники (любого приоритета) в остаток ширины
                rem_w = self.usable_width - row_w
                self._fill_column_stack(current_map, orders, cx, current_y, rem_w, row_h, gap)
                
                current_y += row_h
                mains = [o for o in mains if not o['placed']]

        if current_map: bobbins.append(current_map)
        return self._finalize(bobbins, gap)

    def _fill_column_stack(self, cmap, all_o, x, y, rw, rh, gap):
        """Набивает пустую область справа колонками спутников сверху вниз"""
        curr_x = x
        while rw > 10:
            stack_y = 0
            col_w = 0
            found_any_in_col = False
            
            while stack_y < rh:
                rem_h = rh - stack_y
                # Ищем лучший спутник в это окно
                best_s = None
                sats = [s for s in all_o if not s['placed'] and s['width'] <= (rw - gap)]
                for s in sats:
                    self._check_rotation(s)
                    if s['width'] <= (rw - gap) and s['length'] <= rem_h:
                        best_s = s; break
                
                if best_s:
                    cmap.append(self._create_item(best_s, curr_x, y + stack_y))
                    best_s['placed'] = True
                    col_w = max(col_w, best_s['width'])
                    stack_y += best_s['length'] + (gap/1000)
                    found_any_in_col = True
                else: break
            
            if found_any_in_col:
                rw -= (col_w + gap)
                curr_x += (col_w + gap)
            else: break

    def _check_rotation(self, o):
        rot_w = o['length'] * 1000
        rot_h = o['width'] / 1000
        if rot_w <= self.usable_width and rot_h < o['length']:
            o['width'], o['length'] = rot_w, rot_h
            o['rotated'] = True
        else: o['rotated'] = False

    def _create_item(self, o, x, y):
        return {"id": o['id'], "p": o['priority'], "rotated": o.get('rotated', False), "w": o['width'], "h": o['length'], "y": round(y, 3), "x": x}

    def _finalize(self, bobbins, gap):
        useful = sum(sum(i['w'] * i['h'] for i in b) for b in bobbins) / 1000
        total_l = sum(max((i['y'] + i['h']) for i in b) if b else 0 for b in bobbins)
        total_a = (total_l * 1500) / 1000
        return {"bobbins": bobbins, "config": {"gap": gap}, "metrics": {"useful_m2": useful, "waste_m2": total_a - useful}}
