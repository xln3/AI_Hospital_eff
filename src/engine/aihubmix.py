import os
import openai
from openai import OpenAI
from utils.register import register_class
from .base_engine import Engine
import time


@register_class(alias="Engine.AiHubMix")
class AiHubMixEngine(Engine):
    def __init__(self, aihubmix_api_key, aihubmix_model_name="gpt-5-nano", temperature=0.0, max_tokens=1024, top_p=1, frequency_penalty=0, presence_penalty=0):
        aihubmix_api_key = aihubmix_api_key if aihubmix_api_key is not None else os.environ.get('AIHUBMIX_API_KEY')
        assert aihubmix_api_key is not None, "AIHUBMIX_API_KEY must be provided"

        self.model_name = aihubmix_model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty

        # AiHubMix API configuration
        self.client = OpenAI(
            api_key=aihubmix_api_key,
            base_url="https://aihubmix.com/v1"
        )

    def get_response(self, messages):
        model_name = self.model_name
        i = 0
        response = None
        while i < 5:
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_tokens,
                    top_p=self.top_p,
                    frequency_penalty=self.frequency_penalty,
                    presence_penalty=self.presence_penalty
                )
                break
            except openai.BadRequestError as e:
                print(f"BadRequestError: {e}")
                i += 1
            except openai.RateLimitError:
                print("Rate limit hit, waiting 10 seconds...")
                time.sleep(10)
                i += 1
            except Exception as e:
                print(f"Error: {e}")
                i += 1
                time.sleep(5)
                continue

        if response is None:
            raise Exception(f"Failed to get response after 5 retries")

        return response.choices[0].message.content
