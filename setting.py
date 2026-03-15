from openai import AsyncOpenAI

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator


class Config(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    BOT_TOKEN: str
    ChatGPT_TOKEN: str
    DEBUG: bool = False

    OPENAI_CLIENT: AsyncOpenAI | None = None

    @model_validator(mode="after")
    def create_openai_client(self) -> "Config":
        self.OPENAI_CLIENT = AsyncOpenAI(api_key=self.ChatGPT_TOKEN)
        return self

    model_config = ConfigDict(env_file=".env", arbitrary_types_allowed=True)


config = Config()
