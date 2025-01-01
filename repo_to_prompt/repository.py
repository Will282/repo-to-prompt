from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Optional

from git import Git, GitCommandError, Repo
from pathspec import PathSpec

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
    """
    Handles the processing of Git repositories, either local or remote, and generates structured text outputs
    suitable for large language models (LLMs).

    Attributes:
        repo_input (str): The local path or remote URL of the repository.
        output_dir (Path): Directory where output files will be saved.
        max_tokens (int): Maximum number of tokens allowed per output chunk.
        git_instance (Git): Git instance for running Git commands.
        temp_dir (Optional[TemporaryDirectory]): Temporary directory for cloning remote repositories.
        repo (Repo): The Git repository instance.
        repo_dir (Path): The working directory of the repository.
        ignore_spec (PathSpec): Path specification for ignored files based on `.gitignore` patterns.
    """

    def __init__(
        self,
        repo_input: str,
        output_dir: str,
        max_tokens: int = 2_000_000,
        git_instance: Optional[Git] = None,
    ):
        """
        Initializes the RepositoryHandler instance.

        Args:
            repo_input (str): The local path or remote URL of the Git repository.
            output_dir (str): Directory where output files will be saved.
            max_tokens (int): Maximum tokens allowed per output chunk (default is 2,000,000).
            git_instance (Git, optional): Git instance for executing Git commands. Defaults to None.
        """
        self.repo_input = repo_input
        self.output_dir = Path(output_dir)
        self.max_tokens = max_tokens
        self.git_instance = git_instance or Git()
        self.temp_dir: Optional[TemporaryDirectory] = None
        self.repo = self._get_repo()
        self.repo_dir = Path(self.repo.working_tree_dir)  # type: ignore
        self.ignore_spec = self._load_ignore_patterns()

    def __enter__(self) -> "RepositoryHandler":
        """
        Enters the context manager for the RepositoryHandler.

        Returns:
            RepositoryHandler: The current instance of the RepositoryHandler.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Exits the context manager for the RepositoryHandler and cleans up the temporary directory if it exists.

        Args:
            exc_type (Optional[type[BaseException]]): The exception type.
            exc_value (Optional[BaseException]): The exception instance.
            traceback (Optional[TracebackType]): The traceback object.
        """
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
        """
        Resolves the Git repository, either from a local path or by cloning a remote repository.

        Returns:
            Repo: The Git repository instance.

        Raises:
            ValueError:
                - If the provided path or URL is not a valid repository.
                - If the `working_tree_dir` of the cloned repository is `None`.
        """
        # Handle local repo
        local_path = Path(self.repo_input)
        if local_path.exists():
            repo = Repo(self.repo_input)
        # Handle remote repo
        else:
            try:
                self.git_instance.ls_remote(self.repo_input)
            except GitCommandError as e:
                raise ValueError(f"Invalid repository URL: {self.repo_input}") from e

            self.temp_dir = TemporaryDirectory()
            repo = Repo.clone_from(url=self.repo_input, to_path=self.temp_dir.name)

        if repo.working_tree_dir is None:
            raise ValueError("The repository has no valid working directory.")

        return repo

    def process_repository(self) -> None:
        """
        Processes the repository by generating a tree structure and collecting files, then delegates the splitting and
        saving of files to the OutputGenerator.
        """
        repo_structure = self.generate_tree_structure()
        files = self._collect_files()

        output_generator = OutputGenerator(
            output_dir=self.output_dir,
            max_tokens=self.max_tokens,
        )
        output_generator.split_and_save(repo_structure, files)

    def _load_ignore_patterns(self) -> PathSpec:
        """
        Loads ignore patterns from `.gitignore` and other Git-specific ignore files.

        Returns:
            PathSpec: A compiled PathSpec object containing all ignore patterns.
        """

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
        return PathSpec.from_lines("gitwildmatch", patterns)

    def _collect_files(self) -> list[FileContent]:
        """
        Collects all non-ignored files from the repository, reading their content and paths.

        Returns:
            list[FileContent]: A list of FileContent objects representing the files to be processed.
        """
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

        Returns:
            str: The tree structure as a string.
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

        Args:
            relative_path (Path): The relative path to check.

        Returns:
            bool: True if the path matches an ignore pattern, False otherwise.
        """
        if ".git" in relative_path.parts:
            return True

        # Convert path to POSIX style for matching (required by pathspec)
        path_str = str(relative_path.as_posix())
        return self.ignore_spec.match_file(path_str)
