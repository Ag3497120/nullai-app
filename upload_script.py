from huggingface_hub import upload_folder

folder_path = "/Users/motonishikoudai/project_locate"
repo_id = "kofdai/null-ai"

upload_folder(
    folder_path=folder_path,
    repo_id=repo_id,
    repo_type="model",
    ignore_patterns=["huggingface_model_repo", "venv", "__pycache__", "*.pyc", ".git", ".idea", "*.DS_Store"],
)