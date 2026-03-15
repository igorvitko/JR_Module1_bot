import asyncio

from openai import AsyncOpenAI
import httpx


class ChatGptService:

    def __init__(self, token):
        self.client = AsyncOpenAI(
            # http_client=httpx.AsyncClient(proxy="http://18.199.183.77:49232"),
            api_key=token)
        self.message_list = []

    async def send_message_list(self) -> str:
        completion = await self.client.chat.completions.create(
            # "gpt-3.5-turbo", # gpt-4o,  gpt-4-turbo,    gpt-3.5-turbo, gpt-4o-mini,  GPT-4o mini
            model="gpt-5-mini-2025-08-07",
            messages=self.message_list,
            max_completion_tokens=3000,
            # temperature=0.7,
        )
        message = completion.choices[0].message
        self.message_list.append(message)
        return message.content

    def set_prompt(self, prompt_text: str) -> None:
        self.message_list.clear()
        self.message_list.append({"role": "system", "content": prompt_text})

    async def add_message(self, message_text: str) -> str:
        self.message_list.append({"role": "user", "content": message_text})
        return await self.send_message_list()

    async def send_question(self, prompt_text: str, message_text: str) -> str:
        self.message_list.clear()
        self.message_list.append({"role": "system", "content": prompt_text})
        self.message_list.append({"role": "user", "content": message_text})
        return await self.send_message_list()
