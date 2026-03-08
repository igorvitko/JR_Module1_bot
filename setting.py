from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Config(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    BOT_TOKEN: str
    ChatGPT_TOKEN: str
    DEBUG: bool = False


config = Config()
