"""Application configuration loaded from environment variables.

V1.0 Frozen Baseline — additive changes only for V2.1.
All V2 feature flags default to False and are INERT in this version.
"""

from enum import StrEnum

from pydantic_settings import BaseSettings


class Environment(StrEnum):
    """Application runtime environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Central configuration for the TestGen AI backend.

    Frozen as V1.0 baseline. V2 fields must be ADDITIVE — never rename
    or remove existing fields without a major version bump.
    """

    # ----------------------------------------------------------------
    # Application identity
    # ----------------------------------------------------------------
    PROJECT_NAME: str = "TestGen AI"
    VERSION: str = "2.1.0"
    ARCHITECTURE_VERSION: str = "2.1"
    DESCRIPTION: str = (
        "AI-powered unit test and test oracle generation for Python source code."
    )

    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    LOG_LEVEL: str = "INFO"

    # ----------------------------------------------------------------
    # CORS
    # ----------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ----------------------------------------------------------------
    # Database
    # ----------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./testgen.db"

    # ----------------------------------------------------------------
    # LLM (Gemini)
    # ----------------------------------------------------------------
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_TEMPERATURE: float = 0.3
    GEMINI_MAX_OUTPUT_TOKENS: int = 4096
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 3

    # ----------------------------------------------------------------
    # Input limits
    # ----------------------------------------------------------------
    MAX_SOURCE_CODE_SIZE: int = 50_000   # 50 KB
    MAX_SPECIFICATION_SIZE: int = 10_000  # 10 KB

    # ----------------------------------------------------------------
    # Prompt versioning
    # ----------------------------------------------------------------
    PROMPT_VERSION: str = "v1"

    # ----------------------------------------------------------------
    # V2 Feature flags — ALL default False, completely inert in V1.
    # These flags are placeholders that prepare the config system for
    # V2.1 features. No V1 code reads these values.
    # ----------------------------------------------------------------
    ENABLE_V2_API: bool = True            # V2: V2 API routes active
    ENABLE_SANDBOX: bool = False          # V2: Docker-based test execution
    ENABLE_RAG: bool = False              # V2: Repository context retrieval
    ENABLE_SELF_HEAL: bool = False        # V2: Automatic test repair loop
    ENABLE_REVIEW: bool = False           # V2: LLM-based test review pass
    ENABLE_CONFIDENCE: bool = True        # V2: Confidence scoring per test (Phase 4)
    ENABLE_MULTI_PROVIDER: bool = False   # V2: Multiple LLM providers
    ENABLE_EXPLAINABILITY: bool = False   # V2: Natural-language test explanations
    ENABLE_AUTH: bool = True              # V2: Authentication enforcement (Phase 2)
    ENABLE_L1_CACHE: bool = False         # V2: L1 exact prompt cache (Phase 4)
    ENABLE_L2_CACHE: bool = False         # V2: L2 AST structural cache (Phase 4)

    # ----------------------------------------------------------------
    # V2.2 Test Quality Evaluation & Mutation Analysis Settings
    # Feature flags default to False; inert until enabled in config.
    # ----------------------------------------------------------------
    ENABLE_QUALITY_EVALUATION: bool = False
    ENABLE_MUTATION_TESTING: bool = False
    MUTATION_PROVIDER_CLASS: str = "ast"   # Provider strategy ("ast", "mutmut")
    MUTATION_TIMEOUT_SECONDS: int = 15
    MAX_MUTANTS_PER_FUNCTION: int = 15
    MAX_TEST_FUNCTION_LINES: int = 50

    # Configurable Quality Score Component Weights (must sum to 1.0)
    QUALITY_WEIGHT_COVERAGE: float = 0.25
    QUALITY_WEIGHT_MUTATION: float = 0.35
    QUALITY_WEIGHT_HYGIENE: float = 0.20
    QUALITY_WEIGHT_SEMANTIC: float = 0.20

    # Quality Rating Thresholds
    QUALITY_THRESHOLD_EXCELLENT: float = 90.0
    QUALITY_THRESHOLD_GOOD: float = 80.0
    QUALITY_THRESHOLD_FAIR: float = 60.0

    # ----------------------------------------------------------------
    # L1 Cache — in-memory, thread-safe (Phase 4)
    # ----------------------------------------------------------------
    L1_CACHE_MAX_SIZE: int = 256          # Maximum entries before LRU eviction
    L1_CACHE_TTL_SECONDS: int = 3600      # Time-to-live in seconds (1 hour)

    # ----------------------------------------------------------------
    # L2 Cache — persistent DB cache (Phase 4)
    # ----------------------------------------------------------------
    L2_CACHE_TTL_SECONDS: int = 86400     # Time-to-live in seconds (24 hours)

    # ----------------------------------------------------------------
    # Context Provider (Phase 4)
    # Determines which ContextProvider implementation is used.
    # "default" → DefaultContextProvider (returns empty string).
    # Future values: "rag" → RAG-backed provider (Phase 5+).
    # ----------------------------------------------------------------
    CONTEXT_PROVIDER_CLASS: str = "default"

    # ----------------------------------------------------------------
    # Golden Dataset Evaluation (Phase 4)
    # ----------------------------------------------------------------
    ENABLE_GOLDEN_EVALUATION: bool = False
    GOLDEN_DATASET_PATH: str = ""         # Path to JSON golden dataset file

    # ----------------------------------------------------------------
    # JWT — Phase 2 authentication
    # ----------------------------------------------------------------
    JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_USE_A_LONG_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = 24  # Architecture: 24-hour access tokens

    # ----------------------------------------------------------------
    # Sandbox sidecar — Phase 2/3 execution isolation
    # SANDBOX_URL binds to loopback only — never a public address.
    # ----------------------------------------------------------------
    SANDBOX_URL: str = "http://127.0.0.1:8001"
    SANDBOX_SECRET: str = "CHANGE_THIS_SANDBOX_SECRET_IN_PRODUCTION"
    SANDBOX_TIMEOUT_SECONDS: int = 60
    SANDBOX_MAX_CONCURRENT_CONTAINERS: int = 5
    SANDBOX_CONTAINER_MEMORY_MB: int = 128   # kept for backward compat
    SANDBOX_MEMORY_MB: int = 128             # name used by sandbox/executor.py
    # Docker image for isolated test execution. Must have pytest pre-installed.
    # Build: cd backend && docker build -t testgen-sandbox:latest ./sandbox
    SANDBOX_DOCKER_IMAGE: str = "testgen-sandbox:latest"

    # ----------------------------------------------------------------
    # Derived helpers
    # ----------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.ENVIRONMENT == Environment.TESTING

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
