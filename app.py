# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from evaluator import evaluate_project

app = Flask(__name__)
CORS(app) # Allows the frontend to communicate with the backend

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
    print("🚀 AI Evaluator Server running on http://localhost:5000")
    app.run(debug=True, port=5000)