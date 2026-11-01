from pydantic import BaseModel, Field

class Doc(BaseModel):
    """Document ID for selection."""
    id: int

class ChosenDocuments(BaseModel):
    """List of document IDs chosen from the retrieved documents."""
    list_ids: list[Doc] | None = Field(default=None, description="List of document IDs")

