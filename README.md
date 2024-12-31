# Repo to Prompt (r2p)

## Overview

`Repo to Prompt` (r2p) is a Python CLI tool that converts a local or remote Git repository into a structured set of files for use with LLMs like ChatGPT or Claude. It helps developers generate code reviews, write tests, or optimize repositories by providing a token-limited, chunked representation of the repository structure and content.

## Features

- **Supports Local and Remote Git Repositories**: Automatically clones and processes repositories.
- **Token-Aware Splitting**: Outputs files in chunks, ensuring no chunk exceeds the specified token limit.
- **Customizable**: Configure output directories and token limits with CLI options.
- **Built with Modern Python**: Developed using `click`, `pydantic`, and `gitpython`.

## Installation

### Using [Poetry](https://python-poetry.org/)
```bash
poetry install
```

## Usage

### CLI Command: `r2p`

```bash
r2p [OPTIONS] REPO
```

#### Arguments:
- `REPO`: Path to a local repository or URL of a remote Git repository.

#### Options:
- `--output-dir <path>`: Directory to store the output files (default: `output`).
- `--max-tokens <int>`: Maximum tokens per output file (default: 2,000,000).

#### Examples:
1. **Process a Local Repository**:
   ```bash
   r2p ./my-local-repo --output-dir ./output --max-tokens 100000
   ```

2. **Process a Remote Repository**:
   ```bash
   r2p https://github.com/Will282/ec2-dev-machine --output-dir ./output
   ```

## Development

### Running Tests
```bash
poetry run pytest
```

### Pre-Commit Hooks
Ensure code quality with pre-commit:
```bash
pre-commit run --all-files
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the [MIT License](LICENSE).

## Author

Created by **Will Parr**.
