# server.py — запускать на облачном сервере
import hashlib
import sqlite3
import time
import os
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'blaze-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# База данных (на хостинге будет файл)
conn = sqlite3.connect('blaze.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    online INTEGER DEFAULT 0
)''')
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user TEXT,
    to_user TEXT,
    text TEXT,
    timestamp INTEGER
)''')
conn.commit()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'Все поля обязательны'}), 400
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_pw(password)))
        conn.commit()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Пользователь уже существует'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_pw(password))).fetchone()
    if not user:
        return jsonify({'error': 'Неверные данные'}), 401
    return jsonify({'success': True, 'username': username})

@app.route('/api/users')
def get_users():
    users = c.execute("SELECT username, online FROM users").fetchall()
    return jsonify([{'username': u[0], 'online': u[1]} for u in users])

@app.route('/api/messages/<username>')
def get_messages(username):
    msgs = c.execute('''SELECT from_user, to_user, text, timestamp FROM messages 
                        WHERE from_user = ? OR to_user = ? ORDER BY timestamp''', (username, username)).fetchall()
    return jsonify([{'from': m[0], 'to': m[1], 'text': m[2], 'time': m[3]} for m in msgs])

@socketio.on('join')
def handle_join(data):
    username = data['username']
    c.execute("UPDATE users SET online = 1 WHERE username = ?", (username,))
    conn.commit()
    emit('user_status', {'username': username, 'online': True}, broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    from_user = data['from']
    to_user = data['to']
    text = data['text']
    timestamp = int(time.time())
    c.execute("INSERT INTO messages (from_user, to_user, text, timestamp) VALUES (?, ?, ?, ?)",
              (from_user, to_user, text, timestamp))
    conn.commit()
    emit('new_message', {'from': from_user, 'to': to_user, 'text': text, 'time': timestamp}, room=to_user)
    emit('new_message', {'from': from_user, 'to': to_user, 'text': text, 'time': timestamp}, room=from_user)

@socketio.on('disconnect')
def handle_disconnect():
    # Здесь можно убрать пользователя из онлайна
    pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)