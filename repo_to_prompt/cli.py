import click

from repo_to_prompt.repository import RepositoryHandler


@click.command()
@click.argument("repo", type=str)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="output",
    help="Directory to store the output files",
)
@click.option(
    "--max-tokens",
    type=int,
    default=2_000_000,
    help="Maximum tokens per file (default is 2 million)",
)
def main(repo: str, output_dir: str, max_tokens: int):
    """
    Converts a Git repository into text files suitable for LLM ingestion.

    REPO is the local path or remote URL of the Git repository.
    """
    with RepositoryHandler(
        repo_input=repo,
        output_dir=output_dir,
        max_tokens=max_tokens,
    ) as repo_handler:
        repo_handler.process_repository()


if __name__ == "__main__":
    main()
