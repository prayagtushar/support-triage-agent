from functools import cached_property
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["sarvam", "gemini", "groq", "openrouter"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql://postgres:postgres@localhost:5432/triage"

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai/v1"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    classifier_provider: Provider = "openrouter"
    classifier_model: str = "meta-llama/llama-3.3-70b-instruct"
    classifier_temperature: float = 0.0
    classifier_max_tokens: int = 1024

    drafter_provider: Provider = "sarvam"
    drafter_model: str = "sarvam-105b"
    drafter_temperature: float = 0.3
    # sarvam-105b reasons before answering and bills it as completion tokens
    drafter_max_tokens: int = 4096

    judge_provider: Provider = "gemini"
    judge_model: str = "gemini-3.5-flash-lite"
    judge_temperature: float = 0.0
    judge_max_tokens: int = 2048

    embedding_provider: Provider = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 1536

    llm_timeout_seconds: float = 60.0
    llm_max_transport_retries: int = 2
    llm_max_validation_retries: int = 1
    # a provider may ask us to wait minutes; honour it, but never silently
    llm_max_backoff_seconds: float = 30.0

    gemini_rpm: int = 15
    gemini_tpm: int = 250_000
    # batchEmbedContents bills  item as a request, so this is items per minute
    gemini_embed_rpm: int = 100
    groq_rpm: int = 30
    # the binding constraint on Groq's free tier, not rpm
    groq_tpm: int = 12_000
    sarvam_rpm: int = 60
    sarvam_tpm: int = 0
    openrouter_rpm: int = 20
    openrouter_tpm: int = 0

    retrieval_candidates: int = 20
    retrieval_top_k: int = 5
    rrf_k: int = 60
    weak_retrieval_floor: float = Field(default=0.40, ge=0.0, le=1.0)

    route_auto_reply_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    route_review_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    composite_weight_judge: float = Field(default=0.5, ge=0.0, le=1.0)
    composite_weight_classifier: float = Field(default=0.3, ge=0.0, le=1.0)
    composite_weight_retrieval: float = Field(default=0.2, ge=0.0, le=1.0)

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    eval_concurrency: int = 4
    usd_to_inr: float = 87.0

    hf_token: str = ""

    @model_validator(mode="after")
    def _check_policy_coherence(self) -> "Settings":
        if self.route_review_threshold > self.route_auto_reply_threshold:
            raise ValueError(
                "route_review_threshold must not exceed route_auto_reply_threshold "
                f"(got {self.route_review_threshold} > {self.route_auto_reply_threshold})"
            )

        weight_total = (
            self.composite_weight_judge
            + self.composite_weight_classifier
            + self.composite_weight_retrieval
        )
        if abs(weight_total - 1.0) > 1e-6:
            raise ValueError(f"composite weights must sum to 1.0 (got {weight_total})")

        if self.judge_provider == self.drafter_provider:
            raise ValueError(
                "judge_provider must differ from drafter_provider: a model grading its "
                f"own output exhibits self-preference bias (both are '{self.judge_provider}')"
            )
        return self

    @cached_property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()
