from pydantic import BaseModel, ConfigDict


class FileContent(BaseModel):
    """
    Represents the content of a file, including its path and textual content.

    Attributes:
        path (str): The relative path to the file within the repository.
        content (str): The text content of the file.
    """

    path: str
    content: str

    model_config = ConfigDict(extra="forbid")
