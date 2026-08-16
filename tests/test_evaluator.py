import pytest
from unittest.mock import patch, MagicMock
from evaluator import extract_repo_info, fetch_github_data, generate_ai_evaluation, evaluate_project

def test_extract_repo_info():
    assert extract_repo_info("https://github.com/user/repo") == ("user", "repo")
    assert extract_repo_info("https://github.com/user/repo.git") == ("user", "repo")
    assert extract_repo_info("https://github.com/user/repo/") == ("user", "repo")
    assert extract_repo_info("invalid") == (None, None)

@patch('evaluator.requests.get')
def test_fetch_github_data_success(mock_get):
    mock_repo_resp = MagicMock()
    mock_repo_resp.json.return_value = {"has_issues": True}
    mock_repo_resp.status_code = 200

    mock_readme_resp = MagicMock()
    mock_readme_resp.text = "Mock README"
    mock_readme_resp.status_code = 200

    mock_lang_resp = MagicMock()
    mock_lang_resp.json.return_value = {"Python": 100, "JavaScript": 50}
    mock_lang_resp.status_code = 200

    mock_get.side_effect = [mock_repo_resp, mock_readme_resp, mock_lang_resp]

    data, error = fetch_github_data("user", "repo")
    
    assert error is None
    assert data["has_issues"] is True
    assert data["readme_content"] == "Mock README"
    assert "Python" in data["tech_stack"]

@patch('evaluator.client.chat.completions.create')
def test_generate_ai_evaluation_success(mock_create):
    mock_choice = MagicMock()
    mock_choice.message.content = '{"score": 85, "quality": "Decent 👍", "strengths": ["A"], "improvements": ["B"]}'
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_create.return_value = mock_response

    github_data = {
        "readme_content": "README",
        "tech_stack": ["Python"],
        "has_issues": False
    }

    result = generate_ai_evaluation("user", "repo", "A test app", github_data)
    
    assert result["score"] == 85
    assert result["quality"] == "Decent 👍"
