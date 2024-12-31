from pathlib import Path
from typing import List

from repo_to_prompt.models import FileContent


class OutputGenerator:
    def __init__(self, output_dir: Path, max_tokens: int):
        self.output_dir = output_dir
        self.max_tokens = max_tokens

    def split_and_save(self, repo_structure: str, files: List[FileContent]):
        # Don't worry about chunking this up.
        current_chunk = "Repo Structure:\n\n" f"{repo_structure}" "\n\n"
        current_tokens = self._estimate_tokens(repo_structure)

        file_index = 1

        for file in files:
            file_header = "-" * 120 + "\n" f"File: {file.path}\n"
            file_content = f"```\n{file.content}\n```" "\n\n"
            file_text = file_header + file_content
            file_tokens = self._estimate_tokens(file_text)

            if current_tokens + file_tokens > self.max_tokens:
                self._save_chunk(current_chunk, file_index)
                file_index += 1
                current_chunk = ""
                current_tokens = 0

            current_chunk += file_text
            current_tokens += file_tokens

        if current_chunk:
            self._save_chunk(current_chunk, file_index)

    def _estimate_tokens(self, text: str) -> int:
        # Simple token estimation
        return len(text) // 4

    def _save_chunk(self, chunk: str, index: int):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.output_dir / f"chunk_{index}.txt"
        file_path.write_text(chunk)
