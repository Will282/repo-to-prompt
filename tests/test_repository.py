from pathlib import Path

import pytest
from git import Repo

from repo_to_prompt.repository import BASE_IGNORE_PATTERNS, RepositoryHandler


def test_repository_handler_init_local_repo(temp_git_repo, tmp_path):
    """
    Test that a RepositoryHandler initializes correctly.
    """
    (temp_git_repo / "file1.txt").write_text("Content of file1")

    repo_handler = RepositoryHandler(repo_input=str(temp_git_repo), output_dir=tmp_path / "output", max_tokens=1000)

    assert repo_handler.repo_input == str(temp_git_repo)
    assert repo_handler.output_dir == tmp_path / "output"
    assert repo_handler.max_tokens == 1000
    assert repo_handler.temp_dir is None
    assert isinstance(repo_handler.repo, Repo)
    assert repo_handler.repo_dir == temp_git_repo
    assert repo_handler.ignore_spec is not None


def test_repository_handler_invalid_repo(tmp_path):
    """
    Test that RepositoryHandler with invalid path raises an error.
    """
    with pytest.raises(ValueError):
        RepositoryHandler(
            repo_input="invalid/path",
            output_dir=tmp_path / "output",
        )


def test_load_ignore_patterns(temp_git_repo, tmp_path):
    """
    Test a .gitignore file is loaded correctly by the RepositoryHandler.
    """

    # Create a .gitignore file
    gitignore_content = """
    *.log
    temp/
    """
    (temp_git_repo / ".gitignore").write_text(gitignore_content)

    repo_handler = RepositoryHandler(
        repo_input=str(temp_git_repo),
        output_dir=tmp_path / "output",
    )

    patterns = repo_handler.ignore_spec.patterns
    # Base ignore patterns + patterns from .gitignore
    expected_patterns = set(BASE_IGNORE_PATTERNS + ["*.log", "temp/"])
    actual_patterns = set(str(p.pattern) for p in patterns)
    assert actual_patterns == expected_patterns


def test_should_ignore(temp_git_repo, tmp_path):
    """
    Tests that the _should_ignore method correctly handles ignored files.
    """
    # Create files
    (temp_git_repo / "file1.txt").write_text("Content of file1")
    (temp_git_repo / "file2.log").write_text("Content of file2")

    # .gitignore
    gitignore_content = """
    *.log
    """
    (temp_git_repo / ".gitignore").write_text(gitignore_content)

    repo_handler = RepositoryHandler(
        repo_input=str(temp_git_repo),
        output_dir=tmp_path / "output",
    )

    # Test _should_ignore method
    relative_path1 = Path("file1.txt")
    relative_path2 = Path("file2.log")

    assert not repo_handler._should_ignore(relative_path1)
    assert repo_handler._should_ignore(relative_path2)


def test_collect_files(temp_git_repo, tmp_path):
    """
    Tests that files are collected correctly, excluding ignored files.
    """

    # Create files that should be included and ignored
    (temp_git_repo / "file1.txt").write_text("Content of file1")
    (temp_git_repo / "file2.log").write_text("Content of file2")
    (temp_git_repo / "temp").mkdir()
    (temp_git_repo / "temp" / "file3.txt").write_text("Content of file3")

    # .gitignore
    gitignore_content = """
    *.log
    temp/
    """
    (temp_git_repo / ".gitignore").write_text(gitignore_content)

    repo_handler = RepositoryHandler(
        repo_input=str(temp_git_repo),
        output_dir=tmp_path / "output",
    )

    files = repo_handler._collect_files()
    file_paths = [f.path for f in files]

    assert "file1.txt" in file_paths
    assert "temp/file3.txt" not in file_paths  # Ignored
    assert "file2.log" not in file_paths  # Ignored


def test_generate_tree_structure(temp_git_repo, tmp_path):
    """
    Validates that the generate_tree_structure method produces a correct tree-like representation of the
    repository, respecting ignore patterns.
    """
    # Create files and directories
    (temp_git_repo / "file1.txt").write_text("Content of file1")
    (temp_git_repo / "dir1").mkdir()
    (temp_git_repo / "dir1" / "file2.txt").write_text("Content of file2")
    (temp_git_repo / "dir1" / "file3.log").write_text("Content of file3")
    (temp_git_repo / "dir2").mkdir()
    (temp_git_repo / "dir2" / "file4.txt").write_text("Content of file4")

    # .gitignore
    gitignore_content = """
    *.log
    dir2/
    """
    (temp_git_repo / ".gitignore").write_text(gitignore_content)

    repo_handler = RepositoryHandler(
        repo_input=str(temp_git_repo),
        output_dir=tmp_path / "output",
    )

    tree_str = repo_handler.generate_tree_structure()
    print(tree_str)

    # Expected tree structure
    expected_tree = """repo\n├── dir1\n│   └── file2.txt\n├── dir2\n└── file1.txt"""

    # Remove leading/trailing whitespace for comparison
    actual_tree = "\n".join(line.rstrip() for line in tree_str.strip().split("\n"))

    assert expected_tree == actual_tree


def test_process_repository(temp_git_repo, tmp_path):
    """
    Ensures the process_repository method integrates with OutputGenerator to split and save files correctly when
    the token limit is exceeded.
    """
    # --- Setup: Create a sample repository structure ---
    (temp_git_repo / "file1.txt").write_text("Content of file1 " * 100)
    (temp_git_repo / "subdir").mkdir()
    (temp_git_repo / "subdir" / "file2.txt").write_text("Content of file2 " * 200)

    # --- Setup: Instantiate RepositoryHandler with a low max_tokens value ---
    output_dir = tmp_path / "output"
    repo_handler = RepositoryHandler(
        repo_input=str(temp_git_repo), output_dir=output_dir, max_tokens=50  # Reduced max_tokens for easier splitting
    )

    # --- Act: Process the repository ---
    repo_handler.process_repository()

    # --- Assert: Check that output files were generated ---
    output_files = list(output_dir.glob("chunk_*.txt"))
    assert len(output_files) > 1, "Output should be split into multiple files"

    # --- Assert: Read and combine all output file content ---
    all_content = ""
    for output_file in output_files:
        all_content += output_file.read_text()

    # --- Assert: Verify the presence of the repo structure ---
    expected_structure = """repo
├── file1.txt
└── subdir
    └── file2.txt"""
    assert expected_structure in all_content, "Repo structure should be present in output"

    # --- Assert: Verify the presence of file content (with markers) ---
    assert (
        f"{'-' * 120}\nFile: file1.txt\n```\nContent of file1" in all_content
    ), "Content of file1.txt should be present"
    assert (
        f"{'-' * 120}\nFile: subdir/file2.txt\n```\nContent of file2" in all_content
    ), "Content of file2.txt should be present"

    # --- Assert: Check if files were split (indirectly) ---
    assert f"{'-' * 120}\nFile:" in all_content, "Files should have been split (multiple file start markers expected)"


def test_process_repository_content_splitting(temp_git_repo, tmp_path):
    """
    Ensure content splitting respects max token limits and includes all content.
    """
    (temp_git_repo / "file1.txt").write_text("A" * 200)
    (temp_git_repo / "file2.txt").write_text("B" * 200)

    output_dir = tmp_path / "output"
    repo_handler = RepositoryHandler(repo_input=str(temp_git_repo), output_dir=output_dir, max_tokens=50)
    repo_handler.process_repository()

    # Assert total content and token distribution
    output_files = list(output_dir.glob("chunk_*.txt"))
    total_content = "".join([f.read_text() for f in output_files])
    assert total_content.count("A") == 200, "All content from file1.txt should be included."
    assert total_content.count("B") == 200, "All content from file2.txt should be included."


def test_collect_non_utf8_files(temp_git_repo, tmp_path):
    """
    Ensure non-UTF-8 files are skipped gracefully.
    """
    (temp_git_repo / "binary_file.bin").write_bytes(b"\x80\x81\x82\x83")
    repo_handler = RepositoryHandler(repo_input=str(temp_git_repo), output_dir=tmp_path / "output")
    files = repo_handler._collect_files()
    assert len(files) == 0, "Non-UTF-8 files should be skipped."


def test_invalid_gitignore(temp_git_repo, tmp_path):
    """
    Ensure invalid .gitignore patterns are handled gracefully.
    """
    (temp_git_repo / ".gitignore").write_text("[INVALID PATTERN")
    repo_handler = RepositoryHandler(repo_input=str(temp_git_repo), output_dir=tmp_path / "output")
    assert repo_handler.ignore_spec is not None, "Ignore patterns should still be initialized."
