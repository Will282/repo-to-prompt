import pytest
from git import Repo


@pytest.fixture
def temp_git_repo(tmp_path):
    """
    Fixture to create a temporary Git repository.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    Repo.init(repo_dir)
    yield repo_dir
