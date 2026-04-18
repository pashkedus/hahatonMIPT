import datetime
import copy


class NestingEngine:
    def __init__(self, bobbin_width=1500, bobbin_length=10000, edge_trim=15):
        self.total_width = bobbin_width
        self.max_length = bobbin_length
        self.edge_trim = edge_trim
        self.usable_width = bobbin_width - 2 * edge_trim

    def pack(self, orders, gap, alloy, thickness):
        best_res = None
        min_waste = float('inf')
        thresholds = [x / 100.0 for x in range(60, 100, 1)]

        # Сюда будем собирать данные для Excel
        iteration_logs = []

        for th in thresholds:
            orders_copy = copy.deepcopy(orders)
            res = self._pack_with_threshold(orders_copy, gap, th, alloy, thickness)

            waste_m2 = res['metrics']['waste_m2']
            useful_m2 = res['metrics']['useful_m2']
            waste_perc = round((waste_m2 / (useful_m2 + waste_m2) * 100), 2) if (useful_m2 + waste_m2) > 0 else 0

            # Добавляем строку лога для каждой итерации
            iteration_logs.append({
                "Сплав": alloy,
                "Толщина": thickness,
                "Порог (%)": int(th * 100),
                "Доля обрезков (%)": waste_perc,
                "Площадь обрезков (м2)": round(waste_m2, 2)
            })

            if waste_m2 < min_waste:
                min_waste = waste_m2
                best_res = res
                best_res['best_threshold_pct'] = int(th * 100)
                best_res['iteration_logs'] = iteration_logs # Сохраняем логи внутри результата

        return best_res

    def _pack_with_threshold(self, orders, gap, threshold, alloy, thickness):
        pool = {p: [o for o in orders if o['priority'] == p] for p in set(o['priority'] for o in orders)}
        priorities = sorted(pool.keys())
        for o in orders: o['placed'] = False
        bobbins, current_map, current_y = [], [], 0
        for p in priorities:
            mains = sorted([o for o in pool[p] if not o['placed']], key=lambda x: (x['length'], x['width']),
                           reverse=True)
            while mains:
                mo = mains[0]
                if mo['placed']: mains.pop(0); continue
                self._check_rotation(mo)
                row_items = [mo]
                mo['placed'] = True
                row_w, row_h = mo['width'], mo['length']
                for i in range(1, len(mains)):
                    sub = mains[i]
                    if not sub['placed']:
                        self._check_rotation(sub)
                        if (row_w + gap + sub['width']) <= self.usable_width:
                            if sub['length'] >= row_h * threshold:
                                row_items.append(sub)
                                sub['placed'] = True
                                row_w += gap + sub['width']
                                row_h = max(row_h, sub['length'])
                if current_y + row_h > self.max_length:
                    bobbins.append(current_map)
                    current_map, current_y = [], 0
                cx = self.edge_trim
                for item in row_items:
                    current_map.append(self._create_item(item, cx, current_y))
                    cx += item['width'] + gap
                rem_w = self.usable_width - row_w
                if rem_w > 5:
                    self._fill_residual(current_map, orders, cx, current_y, rem_w, row_h, gap)
                current_y += row_h
                mains = [o for o in mains if not o['placed']]
        if current_map: bobbins.append(current_map)

        # Передаем сплав и толщину для правильного формирования метрик
        return self._finalize(bobbins, gap, alloy, thickness)

    def _fill_residual(self, cmap, all_o, x, y, rw, rh, gap):
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
                stack_y += best_s['length'] + (gap / 1000)
                found_col = True
            if found_col:
                rw -= (col_w + gap)
                curr_x += (col_w + gap)
            else:
                break

    def _check_rotation(self, o):
        if o['length'] * 1000 <= self.usable_width and (o['length'] < o['width'] / 1000):
            o['width'], o['length'] = o['length'] * 1000, o['width'] / 1000
            o['rotated'] = True
        else:
            o['rotated'] = False

    def _create_item(self, o, x, y):
        return {
            "id": o['id'], "p": o['priority'], "rotated": o.get('rotated', False),
            "w_mm": round(o['width'], 1), "h_mm": round(o['length'] * 1000, 1),
            "y": round(y, 3), "x": round(x, 1), "h_m": round(o['length'], 3)
        }

    def _finalize(self, bobbins, gap, alloy, thickness):
        formatted_bobbins = []
        total_useful = 0
        total_waste = 0

        now_str = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        date_str = datetime.datetime.now().strftime('%Y-%m-%d')

        for idx, cmap in enumerate(bobbins):
            useful_area = sum(item['w_mm'] * item['h_m'] for item in cmap) / 1000.0

            # Высчитываем реально использованную длину на бобине для метрик отходов
            used_len = max([item['y'] + item['h_m'] for item in cmap]) if cmap else 0
            used_area = (used_len * self.total_width) / 1000.0

            waste_area = used_area - useful_area
            waste_perc = (waste_area / used_area * 100) if used_area > 0 else 0

            total_useful += useful_area
            total_waste += waste_area

            cutting_map = []
            for item in cmap:
                cutting_map.append({
                    "order_id": item['id'],
                    "type": "main" if item.get('p', 1) == 1 else "satellite",
                    "priority": item.get('p', 1),
                    "coordinates": {
                        "x_start_mm": round(item['x'], 2),
                        "y_start_m": round(item['y'], 4),
                        "width_mm": round(item['w_mm'], 2),
                        "length_m": round(item['h_m'], 4)
                    }
                    # Дублирующие поля 'h' и 'w' удалены, как просил куратор
                })

            batch_id = f"RUN-{date_str}-{idx + 1:03d}"

            formatted_bobbins.append({
                "instruction_metadata": {
                    "batch_id": batch_id,
                    "timestamp": now_str,
                    "factory": "САЗ",
                    "machine_id": "MILL-05"
                },
                "source_material": {
                    "alloy": alloy,
                    "thickness_um": thickness,
                    "bobbin_width_mm": self.total_width,
                    "bobbin_length_m": self.max_length
                },
                "layout_configuration": {
                    "inter_cut_mm": gap,
                    "edge_trim_mm": self.edge_trim
                },
                "cutting_map": cutting_map,
                "efficiency_metrics": {
                    "total_used_area_m2": round(useful_area, 2),
                    "waste_area_m2": round(waste_area, 2),
                    "waste_percentage": round(waste_perc, 2)
                }
            })

        return {
            "bobbins": formatted_bobbins,
            "metrics": {
                "useful_m2": total_useful,
                "waste_m2": total_waste
            }
        }