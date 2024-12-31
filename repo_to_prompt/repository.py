from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import pathspec
from git import Git, GitCommandError, Repo

from repo_to_prompt.models import FileContent
from repo_to_prompt.output import OutputGenerator

BASE_IGNORE_PATTERNS = [
    ".git/*",
    ".gitignore",
    ".gitmodules",
    ".gitattributes",
    # Environment
    ".env",
    ".venv*",
    "env/",
    "venv/",
    "ENV/",
    "env.bak/",
    "venv.bak/",
    # Package locks
    "*.lock",
    "package-lock.json",
]


class RepositoryHandler:
    def __init__(self, repo_input: str, output_dir: str, max_tokens: int = 2_000_000, git_instance=None):
        self.repo_input = repo_input
        self.output_dir = Path(output_dir)
        self.max_tokens = max_tokens
        self.git_instance = git_instance or Git()
        self.temp_dir: Optional[TemporaryDirectory] = None
        self.repo = self._get_repo()
        self.repo_dir = Path(self.repo.working_tree_dir)
        self.ignore_spec = self._load_ignore_patterns()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temp_dir:
            self.temp_dir.cleanup()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"repo_input={self.repo_input!r}, "
            f"repo_dir={self.repo_dir!r}, "
            f"output_dir={str(self.output_dir)!r}, "
            f"max_tokens={self.max_tokens}, "
            f"temp_dir={'True' if self.temp_dir else 'False'})"
        )

    def _get_repo(self) -> Repo:

        if Path(self.repo_input).exists():
            return Repo(self.repo_input)

        is_remote = False
        try:
            self.git_instance.ls_remote(self.repo_input)
            is_remote = True
        except GitCommandError:
            pass

        if is_remote:
            self.temp_dir = TemporaryDirectory()
            return Repo.clone_from(url=self.repo_input, to_path=self.temp_dir.name)
        else:
            raise ValueError(f"Repository at {self.repo_input} is not a valid local or valid remote repository.")

    def process_repository(self):
        repo_structure = self.generate_tree_structure()
        files = self._collect_files()

        output_generator = OutputGenerator(
            output_dir=self.output_dir,
            max_tokens=self.max_tokens,
        )
        output_generator.split_and_save(repo_structure, files)

    def _load_ignore_patterns(self):
        def parse_gitignore_lines(lines: list[str]):
            lines = [line.strip() for line in lines]
            return [line for line in lines if not line.startswith("#")]

        # Init patterns and use base ignore patterns (such as .env)
        patterns = []
        patterns.extend(BASE_IGNORE_PATTERNS)

        # If a .gitignore file exists, load that for ignore.
        gitignore_file = self.repo_dir / ".gitignore"
        if gitignore_file.exists():
            patterns.extend(parse_gitignore_lines(gitignore_file.read_text().splitlines()))

        # Also load patterns from global gitignore if necessary (e.g., .git/info/exclude)
        exclude_file = self.repo_dir / ".git" / "info" / "exclude"
        if exclude_file.exists():
            patterns.extend(parse_gitignore_lines(exclude_file.read_text().splitlines()))

        # Remove any duplicates
        patterns = list(set(patterns))

        # Compile the ignore patterns
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def _collect_files(self) -> list[FileContent]:
        files = []

        all_paths = [p for p in self.repo_dir.rglob("*") if p.is_file()]
        # Get relative paths for matching with pathspec
        relative_paths = [p.relative_to(self.repo_dir) for p in all_paths]

        for relative_path, absolute_path in zip(relative_paths, all_paths):
            # Skip files in the .git directory
            if ".git" in relative_path.parts:
                continue

            # Convert path to POSIX style for matching (required by pathspec)
            path_str = str(relative_path.as_posix())

            if self.ignore_spec.match_file(path_str):
                # File matches ignore patterns, skip it
                continue

            try:
                file_contents = absolute_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Handle files that can't be decoded as UTF-8
                # file_contents = absolute_path.read_bytes().decode('utf-8', errors='replace')
                # Or don't and just skip it!
                continue

            files.append(FileContent(path=str(relative_path), content=file_contents))

        return files

    def generate_tree_structure(self) -> str:
        """
        Generates a tree-like string representation of the repository structure,
        respecting the ignore patterns.
        """
        tree_lines = []

        def build_tree(current_path: Path, prefix: str = ""):
            entries = sorted([p for p in current_path.iterdir() if p.name != ".git"], key=lambda x: x.name)
            entries = [e for e in entries if not self._should_ignore(e.relative_to(self.repo_dir))]

            for index, entry in enumerate(entries):
                connector = "└── " if index == len(entries) - 1 else "├── "
                line = f"{prefix}{connector}{entry.name}"
                tree_lines.append(line)

                if entry.is_dir():
                    extension = "    " if index == len(entries) - 1 else "│   "
                    build_tree(entry, prefix + extension)

        build_tree(self.repo_dir)
        return f"{self.repo_dir.name}\n" + "\n".join(tree_lines)

    def _should_ignore(self, relative_path: Path) -> bool:
        """
        Determines if a given path should be ignored based on the ignore patterns.
        """
        if ".git" in relative_path.parts:
            return True

        # Convert path to POSIX style for matching (required by pathspec)
        path_str = str(relative_path.as_posix())
        return self.ignore_spec.match_file(path_str)


if __name__ == "__main__":
    # projects_path = Path("/home/wparr/projects")
    # repo_path = projects_path / "langchain-aws"

    repo_path = "."

    with RepositoryHandler(repo_input=repo_path, output_dir="./output") as repo_handler:
        repo_handler.process_repository()
