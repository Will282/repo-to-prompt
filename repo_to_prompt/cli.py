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
def main(repo: str, output_dir: str, max_tokens: int) -> None:
    """
    Converts a Git repository into text files suitable for ingestion by large language models.

    This command processes a local or remote Git repository, generating token-limited
    output files containing the repository structure and file content.

    Args:
        repo (str): Path to a local repository or URL of a remote Git repository.
        output_dir (str): Directory where the output files will be saved.
        max_tokens (int): Maximum number of tokens allowed per output file.
    """
    with RepositoryHandler(
        repo_input=repo,
        output_dir=output_dir,
        max_tokens=max_tokens,
    ) as repo_handler:
        repo_handler.process_repository()
