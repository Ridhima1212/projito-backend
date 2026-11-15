# backend/evaluator.py
import json
import os
import urllib.parse
from typing import Any

import requests

from dotenv import load_dotenv
# pyrefly: ignore[missing-import]
from groq import Groq
# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)
load_dotenv()

# Initialize Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def extract_repo_info(github_url: str) -> tuple[str | None, str | None]:
    """Extracts username and repo name, automatically removing .git if present."""
    clean_url = github_url.rstrip("/").replace(".git", "")
    parts = clean_url.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, None


def fetch_github_data(owner: str, repo: str) -> tuple[dict[str, Any] | None, str | None]:
    """Fetches comprehensive repo details: metadata, README, languages, file structure, commits, and package configs."""
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}

    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"

    try:
        repo_resp = requests.get(base_url, headers=headers)
        readme_resp = requests.get(
            f"{base_url}/readme", headers={**headers, "Accept": "application/vnd.github.v3.raw"}
        )
        lang_resp = requests.get(f"{base_url}/languages", headers=headers)

        repo_data = repo_resp.json()
        languages_data = lang_resp.json()

        if "message" in repo_data and repo_data["message"] == "Not Found":
            return None, "Repository not found. Make sure it is public."

        readme_content = (
            readme_resp.text if readme_resp.status_code == 200 else "No README provided."
        )
        tech_stack = (
            list(languages_data.keys())
            if isinstance(languages_data, dict) and languages_data
            else ["None detected"]
        )
        has_issues = repo_data.get("has_issues", False)
        repo_description = repo_data.get("description", "") or "No description provided on GitHub"
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        open_issues = repo_data.get("open_issues_count", 0)
        default_branch = repo_data.get("default_branch", "main")

        # 1. Fetch file tree structure (filter top 60 files)
        file_list: list[str] = []
        tree_resp = requests.get(
            f"{base_url}/git/trees/{default_branch}?recursive=1", headers=headers
        )
        if tree_resp.status_code == 200:
            tree_data = tree_resp.json().get("tree", [])
            for item in tree_data:
                path = item.get("path", "")
                if not any(
                    ignored in path
                    for ignored in [
                        "node_modules/",
                        ".git/",
                        "venv/",
                        "__pycache__/",
                        "dist/",
                        "build/",
                    ]
                ):
                    file_list.append(path)
                if len(file_list) >= 60:
                    break

        # 2. Fetch dependency file content
        dependency_info = "Not found"
        for pkg_path in [
            "package.json",
            "ret/frontend/package.json",
            "frontend/package.json",
            "backend/requirements.txt",
            "requirements.txt",
        ]:
            pkg_resp = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{pkg_path}"
            )
            if pkg_resp.status_code == 200:
                dependency_info = f"File {pkg_path}:\n" + pkg_resp.text[:1200]
                break

        # 3. Fetch recent commits
        commits_resp = requests.get(f"{base_url}/commits?per_page=5", headers=headers)
        recent_commits: list[str] = []
        if commits_resp.status_code == 200:
            for c in commits_resp.json():
                if isinstance(c, dict) and "commit" in c:
                    recent_commits.append(
                        c["commit"].get("message", "").strip().split("\n")[0]
                    )

        return {
            "readme_content": readme_content,
            "tech_stack": tech_stack,
            "has_issues": has_issues,
            "repo_description": repo_description,
            "stars": stars,
            "forks": forks,
            "open_issues": open_issues,
            "file_list": file_list[:50],
            "dependency_info": dependency_info,
            "recent_commits": recent_commits[:5],
        }, None

    except Exception as e:
        return None, f"GitHub API Error: {e!s}"


def enrich_learning_resources(result: dict[str, Any], tech_stack: list[str]) -> dict[str, Any]:
    """Generates guaranteed clickable learning references (YouTube search, Google Docs/Guides, Official Docs) for the project."""
    primary_tech = tech_stack[0] if tech_stack and tech_stack[0] != "None detected" else "Web Development"

    # Known official documentation map for common stacks
    docs_map = {
        "JavaScript": {
            "title": "MDN Web Docs (JavaScript)",
            "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        },
        "TypeScript": {
            "title": "TypeScript Official Handbook",
            "url": "https://www.typescriptlang.org/docs/",
        },
        "Python": {
            "title": "Python 3 Official Documentation",
            "url": "https://docs.python.org/3/",
        },
        "HTML": {
            "title": "MDN HTML Guides",
            "url": "https://developer.mozilla.org/en-US/docs/Web/HTML",
        },
        "CSS": {
            "title": "MDN CSS Reference & Flexbox/Grid",
            "url": "https://developer.mozilla.org/en-US/docs/Web/CSS",
        },
        "React": {
            "title": "React.dev Official Documentation",
            "url": "https://react.dev/learn",
        },
        "Node": {
            "title": "Node.js Official Guides",
            "url": "https://nodejs.org/en/learn",
        },
    }

    # Extract topics from improvements if available
    topics: list[str] = []
    if "improvements" in result and isinstance(result["improvements"], list):
        for imp in result["improvements"][:3]:
            # Take first 5-6 words as keyword query
            words = imp.replace(":", " ").replace('"', "").replace("'", "").split()[:6]
            if words:
                topics.append(" ".join(words))

    if not topics:
        topics = [
            f"{primary_tech} best practices architecture",
            f"{primary_tech} security and testing tutorial",
        ]

    resources: list[dict[str, str]] = []

    # 1. Curated Official Tech Doc
    matched_doc = docs_map.get(
        primary_tech,
        {
            "title": f"{primary_tech} Developer Documentation",
            "url": f"https://www.google.com/search?q={urllib.parse.quote(primary_tech + ' official documentation tutorial')}",
        },
    )
    resources.append({
        "type": "doc",
        "title": matched_doc["title"],
        "description": f"Official documentation and API reference for {primary_tech}.",
        "url": matched_doc["url"],
        "badge": "Official Docs",
    })

    # 2. Targeted YouTube Video Lectures based on top weaknesses
    yt_query = f"{primary_tech} {topics[0]}" if topics else f"{primary_tech} full course tutorial"
    resources.append({
        "type": "youtube",
        "title": f"YouTube Video Lectures: {topics[0] if topics else primary_tech}",
        "description": f"Curated video tutorials & lectures explaining how to implement {topics[0] if topics else primary_tech}.",
        "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}",
        "badge": "YouTube Tutorial",
    })

    # 3. Google Technical Guide / Deep-dive reference
    if len(topics) > 1:
        google_query = f"{primary_tech} {topics[1]} guide tutorial"
        resources.append({
            "type": "guide",
            "title": f"Developer Guides & Articles: {topics[1]}",
            "description": f"In-depth articles, blogs, and step-by-step guides for fixing {topics[1]}.",
            "url": f"https://www.google.com/search?q={urllib.parse.quote(google_query)}",
            "badge": "Google Guide",
        })

    # 4. Architecture / Testing Reference (e.g., Testing, CI/CD, Production standards)
    testing_query = f"{primary_tech} automated testing best practices tutorial"
    resources.append({
        "type": "youtube",
        "title": f"Video Walkthrough: Testing & Production CI/CD for {primary_tech}",
        "description": "Learn how enterprise projects set up unit testing, error boundaries, and deployment pipelines.",
        "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(testing_query)}",
        "badge": "YouTube Walkthrough",
    })

    result["learningResources"] = resources
    return result


def generate_ai_evaluation(
    owner: str, repo: str, user_description: str, github_data: dict[str, Any]
) -> dict[str, Any]:
    """Sends comprehensive repo data to Groq AI and returns an advanced diagnostic audit."""
    safe_readme = github_data["readme_content"][:3000]
    tech_stack = github_data["tech_stack"]
    file_structure = "\n".join(github_data.get("file_list", []))
    dependency_snippet = github_data.get("dependency_info", "None")
    recent_commits = "\n- ".join(github_data.get("recent_commits", ["None"]))

    system_prompt = """
    You are an elite Principal Software Architect and Technical Hiring Manager conducting an in-depth repository audit.
    Your evaluation must be FAIR, METRIC-DRIVEN, and 100% TAILORED to the exact repository submitted.

    SCORING STANDARDS:
    - 80-95: Outstanding full-stack/production projects with clean component architecture, routing, tests, and documentation.
    - 65-79: Solid functional student/portfolio apps with working UI/state/components, even if missing automated tests or CI/CD.
    - 50-64: Early work-in-progress, simple basic scripts, or partial UI without state management.
    - Below 50: Broken, empty, or unorganized starter templates.

    STRICT RULES FOR FEEDBACK:
    1. ZERO GENERIC ADVICE: You MUST directly name actual files, components, context, or libraries found in the repo (e.g. mention actual component names like Navbar.jsx, CartContext.jsx, App.jsx, vite.config.js, etc.).
    2. RECRUITER PITCH: Write an honest 2-sentence pitch a student could use in an interview explaining what this project demonstrates technically.
    3. CATEGORY BREAKDOWN: Provide separate scores (0-100) and specific feedback for:
       - architecture (component structure, routing, clean separation)
       - documentation (README clarity, setup steps)
       - maintainability (code hygiene, modularity, dependencies)
       - security (env variables, input handling, API protection)
    4. TOP PRIORITY FIX: Provide ONE critical code improvement with an actionable copy-pasteable code snippet or terminal command.

    You MUST reply in pure valid JSON matching this exact structure:
    {
        "score": <overall score integer 0-100>,
        "quality": "<Production-Ready 🚀 | Decent 👍 | Needs Refactoring 🛠️ | In Progress ⏳>",
        "recruiterPitch": "<2 concise sentences summarizing the technical strength of this project>",
        "categories": {
            "architecture": {"score": <int>, "feedback": "<specific comment mentioning actual files/components>"},
            "documentation": {"score": <int>, "feedback": "<specific comment on README/setup>"},
            "maintainability": {"score": <int>, "feedback": "<specific comment on packages/code reuse>"},
            "security": {"score": <int>, "feedback": "<specific comment on env/secrets/data safety>"}
        },
        "strengths": [
            "<Specific strength referencing actual file/feature>",
            "<Specific strength referencing actual file/feature>",
            "<Specific strength referencing actual file/feature>"
        ],
        "improvements": [
            "<Actionable improvement customized to this project>",
            "<Actionable improvement customized to this project>",
            "<Actionable improvement customized to this project>"
        ],
        "topPriorityFix": {
            "title": "<Short actionable title>",
            "actionableSnippet": "<Ready-to-use code snippet or command>"
        }
    }
    """

    user_prompt = f"""
    Evaluate this repository in depth:
    - Repository: {owner}/{repo}
    - GitHub Description: {github_data.get('repo_description')}
    - User's Provided Description: {user_description}
    - Primary Languages: {', '.join(tech_stack)}
    
    Actual Project Files in Repository:
    {file_structure if file_structure else "No file list"}

    Dependencies & Config Files:
    {dependency_snippet}

    Recent Commits:
    - {recent_commits}

    README Content:
    {safe_readme}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        ai_response = chat_completion.choices[0].message.content or "{}"
        parsed_result = json.loads(ai_response)
        # Add rich learning resources (YouTube, Google Docs/Guides)
        return enrich_learning_resources(parsed_result, tech_stack)

    except Exception as e:
        print(f"Groq API Error: {e}")
        return {"error": "AI Evaluation failed. Check terminal logs for details."}


def evaluate_project(github_url: str, user_description: str) -> dict[str, Any]:
    """Main entry point: orchestrates GitHub fetch + AI evaluation."""
    owner, repo = extract_repo_info(github_url)
    if not owner or not repo:
        return {"error": "Invalid GitHub URL."}

    github_data, error = fetch_github_data(owner, repo)
    if error or github_data is None:
        return {"error": error or "Failed to fetch repository data."}

    return generate_ai_evaluation(owner, repo, user_description, github_data)
