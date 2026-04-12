import pandas as pd
from flask import Flask, render_template, request, jsonify
import opt

app = Flask(__name__)

def clean_alloy(val):
    """Приводит сплав к чистому строковому виду (например, '1200')"""
    if pd.isna(val): return ""
    return str(val).strip().split('.')[0]

def clean_thick(val):
    """Приводит толщину к числу с плавающей точкой (6,35 -> 6.35)"""
    if pd.isna(val): return 0.0
    try:
        return round(float(str(val).replace(',', '.')), 2)
    except:
        return 0.0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    print("\n[АЭРОКОНДЕНСАТ] Глубокий анализ данных...")
    file = request.files['file']
    
    try:
        # 1. Читаем листы
        df_orders = pd.read_excel(file, sheet_name='Заказы')
        df_ref = pd.read_excel(file, sheet_name='Справочник межкроя')
        
        # 2. Строим справочник с нормализованными ключами
        # Ключ: ("8011", 6.35)
        valid_materials = {}
        for _, r in df_ref.iterrows():
            a = clean_alloy(r['Сплав'])
            t = clean_thick(r['Толщина материала (мкм)'])
            valid_materials[(a, t)] = float(r['Ширина межкройного реза (мм)'])
        
        print(f"[DEBUG] Справочник загружен. Уникальных типов: {len(valid_materials)}")

        engine = opt.NestingEngine()
        all_bobbins_results = []
        global_u_area = 0
        global_w_area = 0

        # 3. Обрабатываем заказы
        # Группируем по исходным колонкам, но внутри будем нормализовать
        groups = df_orders.groupby(['Сплав', 'Толщина материала (мкм)'])

        for (alloy_raw, thick_raw), group_df in groups:
            a_norm = clean_alloy(alloy_raw)
            t_norm = clean_thick(thick_raw)
            
            # ПРОВЕРКА СОПОСТАВЛЕНИЯ
            if (a_norm, t_norm) not in valid_materials:
                print(f"[WARN] Пропуск: {a_norm} / {t_norm}мкм (Нет в справочнике)")
                continue
            
            gap = valid_materials[(a_norm, t_norm)]
            print(f"[LOG] Расчет: {a_norm} | {t_norm}мкм | Рез {gap}мм | Заказов: {len(group_df)}")
            
            mat_orders = []
            for _, r in group_df.iterrows():
                mat_orders.append({
                    "id": str(r['Номер заказа']),
                    "alloy": a_norm,
                    "thickness": t_norm,
                    "width": float(r['Ширина листа заказа (мм)']),
                    "length": float(r['Длина листа заказа (м)']),
                    "priority": int(r['Очередность заказа'])
                })
            
            # Запуск оптимизации
            res = engine.pack(mat_orders, gap)
            
            for b in res['bobbins']:
                all_bobbins_results.append({
                    "material": f"Сплав {a_norm} / {t_norm} мкм",
                    "items": b,
                    "gap": gap
                })
            
            global_u_area += res['metrics']['useful_m2']
            global_w_area += res['metrics']['waste_m2']

        if not all_bobbins_results:
            return jsonify({"error": "Ни один заказ не совпал со справочником. Проверьте названия сплавов и толщину."}), 400

        print(f"[SUCCESS] Готово. Бобин: {len(all_bobbins_results)}")
        
        return jsonify({
            "bobbins": all_bobbins_results,
            "metrics": {
                "eff": round((global_u_area / (global_u_area + global_w_area) * 100), 2),
                "waste": round(global_w_area, 2)
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
