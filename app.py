import pandas as pd
from flask import Flask, render_template, request, jsonify
import logic, logic2, logic3

app = Flask(__name__)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    method = request.form.get('method', 'A')
    
    df = pd.read_excel(file, sheet_name='Заказы')
    df_ref = pd.read_excel(file, sheet_name='Справочник межкроя')
    
    ref = {(str(r['Сплав']), float(str(r['Толщина материала (мкм)']).replace(',','.'))): r['Ширина межкройного реза (мм)'] for _, r in df_ref.iterrows()}
    
    orders = [{"id": str(r['Номер заказа']), "alloy": str(r['Сплав']), "thickness": float(str(r['Толщина материала (мкм)']).replace(',','.')), 
               "width": float(r['Ширина листа заказа (мм)']), "length": float(r['Длина листа заказа (м)']), "priority": int(r['Очередность заказа'])} for _, r in df.iterrows()]

    # Группируем по материалу. Берем самый массовый для примера.
    target = (orders[0]['alloy'], orders[0]['thickness'])
    subset = [o for o in orders if (o['alloy'], o['thickness']) == target]

    if method == 'A': eng = logic.NestingEngine()
    elif method == 'B': eng = logic2.NestingEngine()
    else: eng = logic3.NestingEngine()

    return jsonify(eng.pack(subset, ref))

if __name__ == '__main__': app.run(debug=True)
