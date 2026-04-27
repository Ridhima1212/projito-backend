# backend/evaluator.py
import os
import json
import requests
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def extract_repo_info(github_url):
    """Extracts username and repo name, automatically removing .git if present."""
    clean_url = github_url.rstrip('/').replace('.git', '')
    parts = clean_url.split('/')
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, None

def evaluate_project(github_url, user_description):
    owner, repo = extract_repo_info(github_url)
    if not owner or not repo:
        return {"error": "Invalid GitHub URL."}

    # --- 1. DATA GATHERING (GitHub API) ---
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    try:
        repo_data = requests.get(base_url).json()
        readme_data = requests.get(f"{base_url}/readme", headers={"Accept": "application/vnd.github.v3.raw"})
        languages_data = requests.get(f"{base_url}/languages").json()

        if "message" in repo_data and repo_data["message"] == "Not Found":
            return {"error": "Repository not found. Make sure it is public."}

        # Extract data safely
        readme_content = readme_data.text if readme_data.status_code == 200 else "No README provided."
        tech_stack = list(languages_data.keys()) if languages_data else ["None detected"]
        has_issues = repo_data.get('has_issues', False)

    except Exception as e:
        return {"error": f"GitHub API Error: {str(e)}"}


    # --- 2. RUTHLESS AI TESTING (Groq API) ---
    
    # Truncate README to prevent exceeding AI context limits
    safe_readme = readme_content[:4000] 

    # 🔥 THE NEW, STRICTER AI PERSONALITY 🔥
    system_prompt = """
    You are a ruthlessly strict Senior Staff Software Engineer conducting a rigorous technical audit of a student's portfolio project. 
    You do NOT sugarcoat. Your goal is to expose technical weaknesses and force the developer to think about enterprise-grade standards.

    Evaluate the project aggressively based on:
    1. Documentation (Is it barebones? Missing setup steps or environment variables?)
    2. Architecture & Testing (Are they missing automated tests like Jest/PyTest? Docker containerization? CI/CD pipelines?)
    3. Security & Edge Cases (Are they ignoring basic security practices?)

    CRITICAL INSTRUCTION: Do NOT balance the strengths and improvements. It is highly expected for a college project to have 2 basic Strengths and 5-7 critical Improvements (Weaknesses). Find the flaws! Make the improvements highly technical and demanding.

    You MUST respond in pure JSON format matching this exact structure:
    {
        "score": <integer from 0 to 100 - grade harshly! Average projects should be in the 60s/70s>,
        "quality": "<Choose one: Production-Ready 🚀, Decent 👍, Needs Refactoring 🛠️, or Critical Flaws 🚨>",
        "strengths": ["<string>", "<string>"],
        "improvements": ["<string>", "<string>", "<string>", "<string>", "<string>"]
    }
    """

    user_prompt = f"""
    Evaluate this project mercilessly:
    - Repository: {owner}/{repo}
    - User Description: {user_description}
    - Technologies Used: {', '.join(tech_stack)}
    - Issue Tracking Enabled: {has_issues}
    
    README Snippet:
    {safe_readme}
    """

    try:
        # Call the blazing fast Llama 3.3 model on Groq
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3, # Slightly higher temperature allows it to be more creative with its criticisms
            response_format={"type": "json_object"}
        )

        # Extract and parse the JSON string from the AI
        ai_response = chat_completion.choices[0].message.content
        result = json.loads(ai_response)
        
        return result

    except Exception as e:
        print(f"Groq API Error: {e}")
        return {"error": "AI Evaluation failed. Check terminal logs for details."}