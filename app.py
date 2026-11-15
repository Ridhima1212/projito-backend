# backend/app.py
import os
from dotenv import load_dotenv

# Ensure .env in backend directory is loaded
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db, get_db_connection, is_postgres, save_evaluation, get_user_evaluations, delete_evaluation
from evaluator import evaluate_project, extract_repo_info
from mailer import send_contact_email

app = Flask(__name__)

# Initialize database schema (PostgreSQL or SQLite fallback)
try:
    init_db()
except Exception as e:
    print(f"⚠️ DB initialization warning: {e}")

CORS(app, resources={r"/*": {"origins": "*"}})

# ----------------- 1. AI EVALUATION & HISTORY -----------------
@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.get_json() or {}
    github_url = (data.get('github_url') or '').strip()
    description = (data.get('description') or '').strip()
    user_id = data.get('user_id')

    if not github_url or not description:
        return jsonify({"error": "Please provide both a GitHub URL and a description."}), 400

    result = evaluate_project(github_url, description)
    if not isinstance(result, dict) or result.get("error"):
        return jsonify(result), 400

    # If user is logged in, automatically save to database history
    if user_id:
        try:
            target_uid = None
            if str(user_id).isdigit():
                target_uid = int(user_id)
            elif '@' in str(user_id):
                conn = get_db_connection()
                cursor = conn.cursor()
                param = "%s" if is_postgres() else "?"
                cursor.execute(f"SELECT id FROM users WHERE email = {param}", (str(user_id).strip().lower(),))
                user_row = cursor.fetchone()
                conn.close()
                if user_row:
                    target_uid = user_row['id']

            if target_uid:
                owner, repo = extract_repo_info(github_url)
                repo_name = f"{owner}/{repo}" if owner and repo else github_url
                score = int(result.get('score', 0))
                quality = str(result.get('quality', 'Audited'))
                saved_id = save_evaluation(target_uid, github_url, repo_name, description, score, quality, result)
                result['saved_id'] = saved_id
        except Exception as e:
            print(f"⚠️ Failed to save evaluation history: {e}")

    return jsonify(result)

# ----------------- 1b. GET USER EVALUATION HISTORY -----------------
@app.route('/api/history', methods=['GET'])
def get_history():
    user_id = request.args.get('user_id')
    email = request.args.get('email')

    if not user_id and not email:
        return jsonify({"error": "user_id or email is required."}), 400

    try:
        target_uid = None

        if user_id and str(user_id).isdigit():
            target_uid = int(user_id)
        elif email or (user_id and '@' in str(user_id)):
            target_email = (email or user_id).strip().lower()
            conn = get_db_connection()
            cursor = conn.cursor()
            param = "%s" if is_postgres() else "?"
            cursor.execute(f"SELECT id FROM users WHERE email = {param}", (target_email,))
            user_row = cursor.fetchone()
            conn.close()
            if user_row:
                target_uid = user_row['id']

        if target_uid is None:
            return jsonify({"history": []}), 200

        history = get_user_evaluations(target_uid)
        return jsonify({"history": history}), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

# ----------------- 1c. SAVE EVALUATION TO HISTORY (MANUAL / POST-LOGIN) -----------------
@app.route('/api/history/save', methods=['POST'])
def save_history():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    github_url = (data.get('github_url') or '').strip()
    description = (data.get('description') or '').strip()
    result = data.get('result')

    if not user_id or not github_url or not result:
        return jsonify({"error": "user_id, github_url, and result are required."}), 400

    try:
        owner, repo = extract_repo_info(github_url)
        repo_name = f"{owner}/{repo}" if owner and repo else github_url
        score = int(result.get('score', 0))
        quality = str(result.get('quality', 'Audited'))
        saved_id = save_evaluation(int(user_id), github_url, repo_name, description, score, quality, result)
        return jsonify({"message": "Evaluation saved to history successfully!", "id": saved_id}), 201
    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

# ----------------- 1d. DELETE HISTORY ITEM -----------------
@app.route('/api/history/<int:eval_id>', methods=['DELETE'])
def delete_history_item(eval_id):
    user_id = request.args.get('user_id')
    try:
        deleted = delete_evaluation(eval_id, int(user_id) if user_id else None)
        return jsonify({"message": "History item deleted.", "deleted": deleted}), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {e!s}"}), 500

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
