from pathlib import Path

import pytest
from click.testing import CliRunner

from repo_to_prompt.cli import main
from repo_to_prompt.repository import RepositoryHandler

REMOTE_REPO_URL = "https://github.com/Will282/ec2-dev-machine"


@pytest.mark.integration
def test_remote_repository_with_real_repo(tmp_path):
    """
    Integration test for processing a real remote Git repository.
    """
    output_dir = tmp_path / "output"

    with RepositoryHandler(
        repo_input=REMOTE_REPO_URL,
        output_dir=output_dir,
    ) as repo_handler:
        temp_dir_path = Path(repo_handler.temp_dir.name)

        # Verify the repository was cloned into the temp dir
        assert temp_dir_path.exists(), "Temporary directory should exist during processing."
        assert (temp_dir_path / ".git").exists(), "Cloned repository should contain a .git folder."

        repo_handler.process_repository()

    output_files = list(output_dir.glob("chunk_*.txt"))
    assert len(output_files) > 0, "Processing the remote repository should generate output files."

    all_content = "".join([file.read_text() for file in output_files])
    assert "ec2-dev-machine" in all_content, "Repository structure should include the repo name."
    assert "File:" in all_content, "Output should include file markers indicating file content was processed."
    assert not Path(repo_handler.temp_dir.name).exists(), "Temporary directory should be cleaned up after processing."


@pytest.mark.integration
def test_cli_integration(tmp_path):
    """
    Integration test for the CLI to ensure end-to-end functionality.
    """
    runner = CliRunner()
    result = runner.invoke(
        main,
        [REMOTE_REPO_URL, "--output-dir", str(tmp_path / "output"), "--max-tokens", "50000"],
    )

    assert result.exit_code == 0, "CLI should run successfully."

    output_files = list((tmp_path / "output").glob("chunk_*.txt"))
    assert len(output_files) > 0, "CLI should generate output files."

    all_content = "".join([file.read_text() for file in output_files])
    assert "ec2-dev-machine" in all_content, "Repository structure should be included in the output."
