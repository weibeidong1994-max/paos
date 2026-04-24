import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000


class DatabaseConfig(BaseSettings):
    filename: str = "paos.db"


class LLMFallbackConfig(BaseSettings):
    enabled: bool = True
    mode: str = "agent_queue"


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    max_tokens: int = 2048
    fallback: LLMFallbackConfig = Field(default_factory=LLMFallbackConfig)


class PipelineConfig(BaseSettings):
    default_tags: list[str] = Field(default_factory=lambda: ["未分类"])
    distillation_prompt: str = ""
    auto_generate_article: bool = True


class ArticleOutputConfig(BaseSettings):

    model_config = SettingsConfigDict(env_nested_delimiter="__")
    prompt_template: str = ""
    format: str = "markdown"
    save_dir: str = "./data/output"


class OutputConfig(BaseSettings):

    model_config = SettingsConfigDict(env_nested_delimiter="__")
    article: ArticleOutputConfig = Field(default_factory=ArticleOutputConfig)


class SearchConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    default_engine: str = "duckduckgo"
    auto_search: bool = False
    auto_search_engine: str = "duckduckgo"
    max_results: int = 10
    timeout: float = 15.0
    enrich_pipeline: bool = False


class AdapterConfig(BaseSettings):
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        # env_prefix 已移除：load_settings() 手动合并 env_overrides
        extra="ignore",
    )

    app_name: str = "PAOS"
    app_version: str = "0.2.0"
    data_dir: str = "./data"

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    adapters: AdapterConfig = Field(default_factory=AdapterConfig)

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, self.database.filename)


def _deep_update(original: dict, update: dict) -> dict:
    for key, value in update.items():
        if isinstance(value, dict) and key in original and isinstance(original[key], dict):
            original[key] = _deep_update(original[key], value)
        else:
            original[key] = value
    return original


def load_settings() -> Settings:
    # 加载 .env 文件到 os.environ，确保 PAOS_ 变量可用
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)
        # override=False: 保留已存在的环境变量（如系统级配置）
    config_path = Path(__file__).parent / "default.yaml"
    config_data: dict = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

    # 环境变量覆盖：读取 PAOS_ 前缀的变量并映射到嵌套字典
    env_overrides: dict = {}
    for key, value in os.environ.items():
        if key.startswith("PAOS_"):
            inner_key = key[5:].lower()
            parts = inner_key.split("__")
            target = env_overrides
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = _maybe_convert(value)
        elif key == "OPENAI_API_KEY":
            env_overrides.setdefault("llm", {})["api_key"] = value
        elif key == "OPENAI_BASE_URL":
            env_overrides.setdefault("llm", {})["base_url"] = value
        elif key == "OPENAI_MODEL":
            env_overrides.setdefault("llm", {})["model"] = value

    merged = _deep_update(config_data, env_overrides)
    return Settings(**merged)


def _maybe_convert(value: str) -> Any:
    if value.lower() in ("true", "1"):
        return True
    if value.lower() in ("false", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


settings = load_settings()
