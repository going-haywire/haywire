"""Registry keys owned by haybale-models."""

MODELS_VOLUME = "haybale-models:volume:models"
"""Volume holding model files downloaded or added on this machine."""

HF_VOLUME = "haybale-models:volume:hf-cache"
"""Volume pointing at the shared Hugging Face download cache."""

NEEDS_NOTICE = "haybale-models:needs"
"""Graph-notice key for a graph's list of missing models."""
