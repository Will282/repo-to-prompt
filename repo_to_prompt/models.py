from pydantic import BaseModel, ConfigDict


class FileContent(BaseModel):
    path: str
    content: str

    model_config = ConfigDict(extra="forbid")
