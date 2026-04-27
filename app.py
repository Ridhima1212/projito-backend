# backend/app.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from evaluator import evaluate_project

app = Flask(__name__)

# Netlify ke liye CORS ko explicitly allow kar diya hai
CORS(app, resources={r"/*": {"origins": "*"}}) 

@app.route('/evaluate', methods=['POST'])
def evaluate():
    data = request.get_json()
    github_url = data.get('github_url')
    description = data.get('description')

    if not github_url or not description:
        return jsonify({"error": "Please provide both a GitHub URL and a description."}), 400

    result = evaluate_project(github_url, description)
    return jsonify(result)

if __name__ == '__main__':
    # RENDER FIX: Ye line Render ka dynamic port accept karegi aur '0.0.0.0' se usko public banayegi
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 AI Evaluator Server running on port {port}")
    app.run(host='0.0.0.0', port=port)