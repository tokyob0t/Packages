from typing import ClassVar, Optional


class Config:
    VERSION: str
    APPLICATION_ID: str
    SCHEMA_PATH: str

    _instance: ClassVar[Optional["Config"]] = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            for k, v in kwargs.items():
                setattr(cls, k, v)
        return cls._instance
