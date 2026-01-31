import os

class Config:
    """Конфигурация из переменных окружения."""

    LLM_API_BASE = os.getenv("OPENAI_API_BASE", "http://llm:8000/v1")
    LLM_API_KEY = os.getenv("OPENAI_API_KEY", "sk-dummy")
    LLM_MODEL = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-7B-Instruct")

    MCP_BASH_URL = os.getenv("MCP_BASH_URL", "http://mcp-bash:8081/mcp")
    MCP_PROJECT_URL = os.getenv("MCP_PROJECT_URL", "http://mcp-project:8083/mcp")

    SYSTEM_PROMPT = "You are an intelligent assistant. Use tools when necessary."

    # Этот лимит должен соответствовать --max-model-len в entrypoint_llm.sh
    MAX_MODEL_TOKENS = int(os.getenv("CONTEXT_LENGTH", "0")) or 4096
    # Запас под специальные токены и неточность оценки (headers, stop tokens)
    SAFETY_MARGIN = 200

    MAX_TOOL_TOKENS = int(os.getenv("MAX_TOOL_TOKENS", "0")) or 1024


    @classmethod
    def get_mcp_servers(cls):
        return {
            "bash": {"url": cls.MCP_BASH_URL, "enabled": True},
            "project": {"url": cls.MCP_PROJECT_URL, "enabled": True}
        }
