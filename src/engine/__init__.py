# 注册不同的Engine
from .base_engine import Engine
from .gpt import GPTEngine
from .aihubmix import AiHubMixEngine

# Try to import optional engines
__all__ = ["Engine", "GPTEngine", "AiHubMixEngine"]

try:
    from .chatglm import ChatGLMEngine
    __all__.append("ChatGLMEngine")
except ImportError:
    pass

try:
    from .minimax import MiniMaxEngine
    __all__.append("MiniMaxEngine")
except ImportError:
    pass

try:
    from .wenxin import WenXinEngine
    __all__.append("WenXinEngine")
except ImportError:
    pass

try:
    from .qwen import QwenEngine
    __all__.append("QwenEngine")
except ImportError:
    pass

try:
    from .huatuogpt import HuatuoGPTEngine
    __all__.append("HuatuoGPTEngine")
except ImportError:
    pass

try:
    from .hf import HFEngine
    __all__.append("HFEngine")
except ImportError:
    pass
