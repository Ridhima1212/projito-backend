# backend/app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db_connection, is_postgres
from evaluator import evaluate_project
from mailer import send_contact_email

app = Flask(__name__)

# Initialize database schema (PostgreSQL or SQLite fallback)
try:
    init_db()
except Exception as e:
    print(f"⚠️ DB initialization warning: {e}")

CORS(app, resources={r"/*": {"origins": "*"}})

# ----------------- 1. AI EVALUATION -----------------
@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.get_json() or {}
    github_url = data.get('github_url')
    description = data.get('description')

    if not github_url or not description:
        return jsonify({"error": "Please provide both a GitHub URL and a description."}), 400

    result = evaluate_project(github_url, description)
    return jsonify(result)

# ----------------- 2. AUTHENTICATION: SIGNUP -----------------
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check existing user
        param_placeholder = "%s" if is_postgres() else "?"
        cursor.execute(f"SELECT id FROM users WHERE email = {param_placeholder}", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return jsonify({"error": "An account with this email already exists."}), 409

        # Hash password and insert
        password_hash = generate_password_hash(password)
        if is_postgres():
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id;",
                (name, email, password_hash)
            )
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
                (name, email, password_hash)
            )
            user_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            "message": "User registered successfully!",
            "user": {"id": user_id, "name": name, "email": email}
        }), 201

    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

# ----------------- 3. AUTHENTICATION: LOGIN -----------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param_placeholder = "%s" if is_postgres() else "?"
        cursor.execute(f"SELECT id, name, email, password_hash FROM users WHERE email = {param_placeholder}", (email,))
        user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid email or password."}), 401

        return jsonify({
            "message": "Login successful!",
            "user": {"id": user["id"], "name": user["name"], "email": user["email"]}
        }), 200

    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

# ----------------- 4. CREATE CONTACT (STORE IN POSTGRESQL / SQLITE) -----------------
@app.route('/api/contact', methods=['POST'])
def create_contact():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    subject = (data.get('subject') or 'General Enquiry').strip()
    message = (data.get('message') or '').strip()

    if not name or not email or not message:
        return jsonify({"error": "Name, email, and message are required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if is_postgres():
            cursor.execute(
                "INSERT INTO contacts (name, email, subject, message) VALUES (%s, %s, %s, %s) RETURNING id;",
                (name, email, subject, message)
            )
            contact_id = cursor.fetchone()['id']
        else:
            cursor.execute(
                "INSERT INTO contacts (name, email, subject, message) VALUES (?, ?, ?, ?);",
                (name, email, subject, message)
            )
            contact_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Send email notification to inbox
        email_sent = send_contact_email(name, email, subject, message)

        return jsonify({
            "message": "Message sent successfully! We will get back to you soon.",
            "contact_id": contact_id,
            "email_sent": email_sent
        }), 201

    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

# ----------------- 5. GET ALL CONTACTS -----------------
@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, subject, message, created_at FROM contacts ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()

        contacts = [dict(row) for row in rows]
        return jsonify({"contacts": contacts}), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 AI Evaluator Server running on port {port}")
    app.run(host='0.0.0.0', port=port)
