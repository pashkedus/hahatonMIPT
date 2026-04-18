import pandas as pd
from flask import Flask, render_template, request, jsonify
import opt
import traceback
import json
import os

app = Flask(__name__)


def clean_val(val):
    if pd.isna(val): return ""
    return str(val).strip().split('.')[0]


def clean_float(val):
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
    file = request.files['file']
    try:
        df_orders = pd.read_excel(file, sheet_name='Заказы')
        df_ref = pd.read_excel(file, sheet_name='Справочник межкроя')

        valid_ref = {}
        for _, r in df_ref.iterrows():
            valid_ref[(clean_val(r['Сплав']), clean_float(r['Толщина материала (мкм)']))] = float(
                r['Ширина межкройного реза (мм)'])

        engine = opt.NestingEngine()
        all_results = []
        g_useful, g_waste = 0, 0

        full_optimization_log = []  # Для всех итераций
        group_summary = []  # Для итогов по группам

        groups = df_orders.groupby(['Сплав', 'Толщина материала (мкм)'])

        for (a_raw, t_raw), g_df in groups:
            a_n, t_n = clean_val(a_raw), clean_float(t_raw)
            if (a_n, t_n) not in valid_ref: continue

            gap = valid_ref[(a_n, t_n)]
            mat_orders = [{"id": str(r['Номер заказа']), "width": float(r['Ширина листа заказа (мм)']),
                           "length": float(r['Длина листа заказа (м)']), "priority": int(r['Очередность заказа'])} for
                          _, r in g_df.iterrows()]

            # Получаем результат с логами итераций
            res = engine.pack(mat_orders, gap, a_n, t_n)
            all_results.extend(res['bobbins'])

            # 1. Собираем подробный лог перебора (то, что было в TXT)
            full_optimization_log.extend(res['iteration_logs'])

            # 2. Собираем итог по группе
            g_useful += res['metrics']['useful_m2']
            g_waste += res['metrics']['waste_m2']
            group_summary.append({
                "Сплав": a_n, "Толщина": t_n,
                "Лучший порог (%)": res['best_threshold_pct'],
                "Мин. отход (м2)": round(res['metrics']['waste_m2'], 2)
            })

        # --- ЗАПИСЬ В EXCEL ---
        with pd.ExcelWriter('AeroRusal_Detailed_Report.xlsx') as writer:
            # Лист 1: Общий итог
            waste_total_perc = round((g_waste / (g_useful + g_waste) * 100), 2) if (g_useful + g_waste) > 0 else 0
            pd.DataFrame([
                {"Показатель": "Глобальная доля обрезков", "Значение": f"{waste_total_perc}%"},
                {"Показатель": "Глобальная площадь обрезков", "Значение": f"{round(g_waste, 2)} м2"}
            ]).to_excel(writer, sheet_name='Глобальный итог', index=False)

            # Лист 2: Итоги по группам (Сплав/Толщина)
            pd.DataFrame(group_summary).to_excel(writer, sheet_name='Итоги по группам', index=False)

            # Лист 3: Полный лог (Тот самый TXT формат в виде таблицы)
            pd.DataFrame(full_optimization_log).to_excel(writer, sheet_name='Лог оптимизации (итерации)', index=False)

        # Сохраняем JSON
        with open('AeroRusal_Plan.json', 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        return jsonify({
            "bobbins": all_results,
            "metrics": {
                "waste_perc": waste_total_perc,
                "useful_m2": round(g_useful, 2),
                "waste_m2": round(g_waste, 2),
                "best_threshold_pct": group_summary[-1]['Лучший порог (%)'] if group_summary else 0
            }
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
