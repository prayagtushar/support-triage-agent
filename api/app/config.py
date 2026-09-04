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

    # A speed bump for crawlers, not auth. Empty disables it; the daily cap is the real ceiling.
    demo_write_key: str = ""
    max_tickets_per_day: int = 50

    # What business these tickets belong to. The classifier and the drafter both need it:
    # "my order has not arrived" means something different to a retailer and a bank. It is
    # a setting rather than a phrase inside a prompt so that adopting this is a config
    # change, and so that /policy can state the assumption the numbers were measured under.
    domain: str = "a consumer online shopping service"

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

    # Was sarvam-105b, which is what every eval report in this repo was measured with.
    # Moved off it on 2026-09-04 because the account ran out of credit and a drafter that
    # returns 402 is a demo that fails for every visitor who submits a ticket. The
    # measurements it produced stand; they are attributed to the model in each report.
    #
    # This is also the model the voice work picked on its own merits: sarvam-105b reasons
    # before answering and bills it as completion tokens, so on a call it emits nothing
    # speakable for six seconds. See docs/VOICE.md.
    drafter_provider: Provider = "openrouter"
    drafter_model: str = "meta-llama/llama-3.3-70b-instruct"
    drafter_temperature: float = 0.3
    # Sized for sarvam-105b, which spent most of a budget this large on reasoning: 4096
    # held all 60 golden drafts on 2026-08-01 and only 37 of 60 on 2026-09-03, the other
    # 23 returning empty after spending the whole budget thinking. A truncated call is
    # billed for the reasoning it discards, so the tight budget was the expensive one
    # (₹0.0958 per usable draft against ₹0.0658 at 8192).
    #
    # It costs nothing to leave high for a non-reasoning drafter, which stops at its reply
    # and bills only the tokens it generated.
    drafter_max_tokens: int = 16384

    judge_provider: Provider = "openrouter"
    judge_model: str = "google/gemini-2.5-flash-lite"
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

    route_auto_reply_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    route_review_threshold: float = Field(default=0.55, ge=0.0, le=1.0)

    composite_weight_judge: float = Field(default=0.5, ge=0.0, le=1.0)
    composite_weight_classifier: float = Field(default=0.3, ge=0.0, le=1.0)
    composite_weight_retrieval: float = Field(default=0.2, ge=0.0, le=1.0)

    # Voice. Sarvam's speech endpoints, reached with the same key as the chat model.
    # Speech runs on Sarvam and nothing else does. When that account has no credit the
    # key is still present and still valid, so the endpoints answer 402 rather than
    # failing to authenticate, and there is no way to detect it short of spending a
    # call. This switch says so out loud instead: the page shows the measurements and
    # explains itself, rather than offering a button that errors after asking for a
    # microphone. Set VOICE_ENABLED=true once the account is funded.
    voice_enabled: bool = True
    stt_model: str = "saaras:v3"
    # The corpus is English and Hinglish, so let the provider decide rather than force one.
    stt_language: str = "unknown"
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "ritu"
    tts_language: str = "en-IN"
    tts_sample_rate: int = 22050
    # bulbul:v3's per-request ceiling. A spoken reply never comes close.
    tts_max_chars: int = 2500
    voice_timeout_seconds: float = 30.0
    # How much text must accumulate before a sentence is worth speaking. There is a real
    # tension here and the number should be measured rather than argued: a short opener
    # costs a whole TTS round trip for a moment of audio, and also gets a voice into the
    # caller's ear sooner, which is the thing being optimised. Lower favours latency.
    tts_min_sentence_chars: int = 40

    # The latency cuts, as switches, so one benchmark can measure every arm and each
    # cut can be read separately. All off is the honest baseline: the text pipeline,
    # unchanged, with a microphone on it.
    voice_judge_async: bool = False
    voice_stream_draft: bool = False
    voice_fast_drafter: bool = False

    # Measured, not assumed. sarvam-105b reasons before it answers, and that reasoning
    # is emitted before any speakable token, so streaming cannot start early: first
    # visible word at 6.2s against 1.7s for a non-reasoning model of the same size.
    # Worse, at a tight budget the reasoning consumes the whole allowance and the reply
    # is empty, which on a call is silence rather than a truncation the reviewer sees.
    # Excellent for a queue, wrong for a phone.
    voice_drafter_provider: Provider = "openrouter"
    voice_drafter_model: str = "meta-llama/llama-3.3-70b-instruct"
    voice_drafter_max_tokens: int = 512

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

        # Checked on the model rather than the provider. The rule being enforced is that
        # nothing grades its own output, and the thing that writes and the thing that
        # grades are models, not gateways: Meta's llama and Google's gemini reached
        # through one OpenRouter key are still two vendors. Checking the provider name
        # instead used to reject that pair, which is a correct configuration.
        if self.voice_fast_drafter and self.voice_drafter_model == self.judge_model:
            raise ValueError(
                "voice_drafter_model must differ from judge_model: a model grading its "
                f"own output exhibits self-preference bias (both are '{self.judge_model}')"
            )

        if self.judge_model == self.drafter_model:
            raise ValueError(
                "judge_model must differ from drafter_model: a model grading its "
                f"own output exhibits self-preference bias (both are '{self.judge_model}')"
            )
        return self

    @cached_property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


settings = Settings()
