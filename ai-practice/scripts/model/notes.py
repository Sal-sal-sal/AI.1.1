from pydantic import BaseModel, Field
class Note(BaseModel):
    id: int  = Field(..., ge=1, le=10)
    heading: str  = Field(..., example="Теорема о непрерывности ")       
    summary: str  = Field(..., max_length=150)     
    page_ref: int | None   = Field(None, description="Page number in source PDF")