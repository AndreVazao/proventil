from flask import Flask, request, jsonify, render_template, session, redirect
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import stripe

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key')

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_tua_chave')

# Database setup
db_path = 'db/proventil.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
cur = conn.cursor()

# USERS
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT
)''')

# SETTINGS (preços, margens, percentuais)
cur.execute('''CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)''')
cur.execute('''INSERT OR IGNORE INTO settings (key, value) VALUES
    ('basePrice', '500'),
    ('percentage', '20'),
    ('deslocacao_0_10', '25'),
    ('deslocacao_10_25', '25'),
    ('deslocacao_25_40', '25'),
    ('deslocacao_40', '50')
''')

# TRAVEL PRICES
cur.execute('''CREATE TABLE IF NOT EXISTS travel_prices (
    distance_km INTEGER PRIMARY KEY,
    price REAL
)''')

# PHOTOS
cur.execute('''CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY,
    data TEXT
)''')

# QUOTES
cur.execute('''CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    type TEXT,
    distance INTEGER,
    total REAL,
    paid INTEGER DEFAULT 0
)''')

# BUILDINGS (Prédios / Vivendas)
cur.execute('''CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY,
    name TEXT,
    address TEXT,
    system_type TEXT,  -- audio | video
    installation_date TEXT,
    link_id TEXT UNIQUE
)''')

# APARTMENTS (Frações)
cur.execute('''CREATE TABLE IF NOT EXISTS apartments (
    id INTEGER PRIMARY KEY,
    building_id INTEGER,
    fraction TEXT,
    FOREIGN KEY(building_id) REFERENCES buildings(id)
)''')

# WORKS (Obras / Intervenções)
cur.execute('''CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY,
    building_id INTEGER,
    type TEXT,  -- installation | maintenance | upgrade
    status TEXT, -- pending | approved | completed
    total REAL,
    created_at TEXT,
    FOREIGN KEY(building_id) REFERENCES buildings(id)
)''')

# TEAMS
cur.execute('''CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    name TEXT
)''')

# TECHNICIANS
cur.execute('''CREATE TABLE IF NOT EXISTS technicians (
    id INTEGER PRIMARY KEY,
    name TEXT
)''')

# TEAM MEMBERS
cur.execute('''CREATE TABLE IF NOT EXISTS team_members (
    team_id INTEGER,
    technician_id INTEGER
)''')

# VEHICLES
cur.execute('''CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY,
    name TEXT,
    gps_tracker_id TEXT,
    team_id INTEGER
)''')

conn.commit()

# --------------------- ROUTES ---------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/extraction')
def extraction():
    return render_template('extraction.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        password = request.form['password']
        cur.execute('SELECT * FROM users WHERE username=? AND password=?', (user, password))
        if cur.fetchone():
            session['user'] = user
            return redirect('/dashboard')
        return 'Erro login'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# API: Settings
@app.route('/api/settings', methods=['GET', 'POST'])
def settings_api():
    if 'user' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    if request.method == 'POST':
        data = request.json
        for key in ['basePrice', 'percentage', 'deslocacao_0_10', 'deslocacao_10_25', 'deslocacao_25_40', 'deslocacao_40']:
            cur.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, data.get(key)))
        conn.commit()
        return jsonify({'success': True})
    cur.execute('SELECT * FROM settings')
    res = {row[0]: row[1] for row in cur.fetchall()}
    return jsonify(res)

# API: Photos
@app.route('/api/photos', methods=['GET', 'POST'])
def photos_api():
    if request.method == 'POST':
        data = request.json['data']
        cur.execute('INSERT INTO photos (data) VALUES (?)', (data,))
        conn.commit()
        return jsonify({'success': True})
    cur.execute('SELECT data FROM photos')
    return jsonify([row[0] for row in cur.fetchall()])

# API: Quote
@app.route('/api/quote', methods=['POST'])
def quote_api():
    data = request.json
    tipo = data['type']
    distance = int(data['distance'])

    # Base price e margens
    cur.execute('SELECT value FROM settings WHERE key="basePrice"')
    base = float(cur.fetchone()[0])
    cur.execute('SELECT value FROM settings WHERE key="percentage"')
    perc = float(cur.fetchone()[0]) / 100

    # Deslocação
    if distance <= 10:
        desloc = float(cur.execute('SELECT value FROM settings WHERE key="deslocacao_0_10"').fetchone()[0])
    elif distance <= 25:
        desloc = float(cur.execute('SELECT value FROM settings WHERE key="deslocacao_10_25"').fetchone()[0])
    elif distance <= 40:
        desloc = float(cur.execute('SELECT value FROM settings WHERE key="deslocacao_25_40"').fetchone()[0])
    else:
        desloc = float(cur.execute('SELECT value FROM settings WHERE key="deslocacao_40"').fetchone()[0])

    extra = 300 if tipo == 'extraction' else 0
    total = base + (base * perc) + desloc + extra

    # Insert quote
    cur.execute('INSERT INTO quotes (type, distance, total) VALUES (?, ?, ?)', (tipo, distance, total))
    conn.commit()
    quote_id = cur.lastrowid

    return jsonify({'total': total, 'quote_id': quote_id, 'nota': 'Varia com temporada/materiais'})

# Stripe Payment
@app.route('/api/pay/<quote_id>', methods=['POST'])
def pay(quote_id):
    try:
        cur.execute('SELECT total FROM quotes WHERE id=?', (quote_id,))
        total = cur.fetchone()[0]
        intent = stripe.PaymentIntent.create(
            amount=int(total*100),
            currency='eur',
            payment_method_types=['card']
        )
        return jsonify({'client_secret': intent['client_secret']})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/confirm_pay/<quote_id>', methods=['POST'])
def confirm_pay(quote_id):
    cur.execute('UPDATE quotes SET paid=1 WHERE id=?', (quote_id,))
    conn.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)

import uuid

@app.route('/api/building', methods=['POST'])
def create_building():
    if 'user' not in session:
        return jsonify({'error': 'Não autenticado'}), 401

    data = request.json
    link_id = str(uuid.uuid4())[:8]

    cur.execute('''
        INSERT INTO buildings (name, address, system_type, installation_date, link_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data['name'],
        data['address'],
        data['system_type'],
        data['installation_date'],
        link_id
    ))
    conn.commit()

    return jsonify({'success': True, 'link_id': link_id})

@app.route('/api/building_by_address', methods=['POST'])
def building_by_address():
    data = request.json
    address = data['address']

    cur.execute('SELECT id, name, system_type, installation_date FROM buildings WHERE address=?', (address,))
    row = cur.fetchone()

    if not row:
        return jsonify({'found': False})

    return jsonify({
        'found': True,
        'building_id': row[0],
        'name': row[1],
        'system_type': row[2],
        'installation_date': row[3]
    })

@app.route('/api/work', methods=['POST'])
def create_work():
    if 'user' not in session:
        return jsonify({'error': 'Não autenticado'}), 401

    data = request.json

    cur.execute('''
        INSERT INTO works (building_id, type, status, total, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        data['building_id'],


        data['type'],
        'pending',
        data['total'],
        datetime.now().strftime("%Y-%m-%d")
    ))

    conn.commit()
    return jsonify({'success': True})

@app.route('/videoporteiro')
def videoporteiro():
    return render_template('videoporteiro.html')
