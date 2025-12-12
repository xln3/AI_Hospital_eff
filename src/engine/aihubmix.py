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

        # Models that don't support frequency_penalty and presence_penalty
        models_without_penalties = [
            "grok-4-1-fast-reasoning",
            "gemini-2.5-flash-lite",
            "qwen-turbo-latest",
            "DeepSeek-V3.2-Exp-Think"
        ]

        while i < 5:
            try:
                api_params = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_completion_tokens": self.max_tokens,
                    "top_p": self.top_p,
                }

                # Only add penalty parameters for models that support them
                if model_name not in models_without_penalties:
                    api_params["frequency_penalty"] = self.frequency_penalty
                    api_params["presence_penalty"] = self.presence_penalty

                response = self.client.chat.completions.create(**api_params)
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

    def get_response_with_tokens(self, messages):
        """Get response and return both content and token usage.

        Returns:
            tuple: (content, token_usage_dict) where token_usage_dict contains:
                - prompt_tokens: Number of tokens in the input
                - completion_tokens: Number of tokens in the output
                - total_tokens: Total tokens used
        """
        model_name = self.model_name
        i = 0
        response = None

        # Models that don't support frequency_penalty and presence_penalty
        models_without_penalties = [
            "grok-4-1-fast-reasoning",
            "gemini-2.5-flash-lite",
            "qwen-turbo-latest",
            "DeepSeek-V3.2-Exp-Think"
        ]

        while i < 5:
            try:
                api_params = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_completion_tokens": self.max_tokens,
                    "top_p": self.top_p,
                }

                # Only add penalty parameters for models that support them
                if model_name not in models_without_penalties:
                    api_params["frequency_penalty"] = self.frequency_penalty
                    api_params["presence_penalty"] = self.presence_penalty

                response = self.client.chat.completions.create(**api_params)
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
        # print(f"[DEBUG] response.usage: {response.usage}")
        if response.usage:
            token_usage = {
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(response.usage, 'completion_tokens', 0) ,
                "total_tokens": getattr(response.usage, 'total_tokens', 0)
            }
        else:
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        # print(f"[DEBUG] Extracted token_usage: {token_usage}\n")

        return response.choices[0].message.content, token_usage
