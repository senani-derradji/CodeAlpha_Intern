from pydantic import BaseModel, field_validator

class UrlCreate(BaseModel):
    original_url: str
    @field_validator('original_url')
    def validate_url(cls, v):
        if not v.startswith('http://') and not v.startswith('https://'):
            v = 'http://' + v

        if len(v) > 2048:
            raise ValueError('URL is too long')

        return v


    class Config:
        from_attributes = True