from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Config:
    VERSION: int
    APPLICATION_ID: str
    SCHEMA_PATH: str
