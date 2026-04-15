import pandas as pd
from flask import Flask, render_template, request, jsonify
import opt
import traceback

app = Flask(__name__)

def clean_val(val):
    if pd.isna(val): return ""
    return str(val).strip().split('.')[0]

def clean_float(val):
    if pd.isna(val): return 0.0
    try: return round(float(str(val).replace(',', '.')), 2)
    except: return 0.0

@app.route('/')
def index(): return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    print("\n[АЭРОКОНДЕНСАТ] Старт обработки файла...")
    file = request.files['file']
    try:
        df_orders = pd.read_excel(file, sheet_name='Заказы')
        df_ref = pd.read_excel(file, sheet_name='Справочник межкроя')
        
        valid_ref = {}
        for _, r in df_ref.iterrows():
            a = clean_val(r['Сплав'])
            t = clean_float(r['Толщина материала (мкм)'])
            valid_ref[(a, t)] = float(r['Ширина межкройного реза (мм)'])

        engine = opt.NestingEngine()
        all_results = []
        g_useful, g_waste = 0, 0

        groups = df_orders.groupby(['Сплав', 'Толщина материала (мкм)'])
        for (a_raw, t_raw), g_df in groups:
            a_n, t_n = clean_val(a_raw), clean_float(t_raw)
            if (a_n, t_n) not in valid_ref:
                print(f"[WARN] Пропуск {a_n}/{t_n} - нет в справочнике")
                continue
            
            gap = valid_ref[(a_n, t_n)]
            print(f"[LOG] Расчет: {a_n} | {t_n}мкм | Рез {gap}мм")
            
            mat_orders = [{"id": str(r['Номер заказа']), "alloy": a_n, "thickness": t_n, "width": float(r['Ширина листа заказа (мм)']), "length": float(r['Длина листа заказа (м)']), "priority": int(r['Очередность заказа'])} for _, r in g_df.iterrows()]
            
            res = engine.pack(mat_orders, gap)
            for b in res['bobbins']:
                all_results.append({"material": f"{a_n} / {t_n} мкм", "items": b, "gap": gap})
            
            g_useful += res['metrics']['useful_m2']
            g_waste += res['metrics']['waste_m2']

        if not all_results:
            return jsonify({"error": "Данные не совпали со справочником!"}), 400

        print(f"[SUCCESS] Готово. Создано бобин: {len(all_results)}")
        return jsonify({
            "bobbins": all_results,
            "metrics": {
                "eff": round((g_useful / (g_useful + g_waste) * 100), 2),
                "waste_perc": round((g_waste / (g_useful + g_waste) * 100), 2),
                "waste_m2": round(g_waste, 2)
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
