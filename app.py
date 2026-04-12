import pandas as pd
from flask import Flask, render_template, request, jsonify
import logic
import logic2

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не выбран"}), 400
    
    file = request.files['file']
    method = request.form.get('method', 'A')
    
    try:
        # Читаем данные из Excel
        df_orders = pd.read_excel(file, sheet_name='Заказы')
        df_ref = pd.read_excel(file, sheet_name='Справочник межкрой')
        
        # Парсим справочник межкройного реза
        inter_cut_map = {}
        for _, row in df_ref.iterrows():
            key = (str(row['Сплав']), float(str(row['Толщина материала (мкм)']).replace(',', '.')))
            inter_cut_map[key] = float(row['Ширина межкройного реза (мм)'])

        # Парсим заказы
        orders = []
        for _, row in df_orders.iterrows():
            orders.append({
                "id": str(row['Номер заказа']),
                "alloy": str(row['Сплав']),
                "thickness": float(str(row['Толщина материала (мкм)']).replace(',', '.')),
                "width": float(row['Ширина листа заказа (мм)']),
                "length": float(row['Длина листа заказа (м)']),
                "priority": int(row['Очередность заказа'])
            })

        if not orders:
            return jsonify({"error": "В файле нет заказов"}), 400

        # Берем первый сплав/толщину из списка (одна бобина = один тип материала)
        target_alloy = orders[0]['alloy']
        target_thick = orders[0]['thickness']
        filtered_orders = [o for o in orders if o['alloy'] == target_alloy and o['thickness'] == target_thick]

        # Выбираем алгоритм
        if method == 'A':
            engine = logic.NestingEngine()
        else:
            engine = logic2.NestingEngine()
            
        result = engine.pack(filtered_orders, inter_cut_map)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
