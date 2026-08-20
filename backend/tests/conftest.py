import os

os.environ.setdefault("APP_ENV", "test")
if os.environ.get("RUN_DATABASE_TESTS") != "1":
    os.environ.setdefault("POSTGRES_USER", "test")
    os.environ.setdefault("POSTGRES_PASSWORD", "test")
    os.environ.setdefault("POSTGRES_DB", "test")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ["MARKET_WATCHLIST"] = "AAPL,MSFT,NVDA,GOOGL,AMZN"
os.environ["MARKET_EXCHANGE"] = "US"
os.environ["MARKET_API_BASE_URL"] = "https://market.test/api/v1"
os.environ["FINNHUB_API_KEY"] = "test-api-key"
os.environ["MARKET_REQUEST_TIMEOUT_SECONDS"] = "5"
os.environ["MARKET_CACHE_TTL_SECONDS"] = "300"
os.environ["MARKET_STALE_TTL_SECONDS"] = "1800"
os.environ["NEWS_ARTICLES_PER_CATEGORY"] = "6"
os.environ["NEWS_REQUEST_TIMEOUT_SECONDS"] = "8"
os.environ["NEWS_MAXIMUM_FEED_BYTES"] = "1000000"
os.environ["NEWS_CACHE_TTL_SECONDS"] = "900"
os.environ["NEWS_STALE_TTL_SECONDS"] = "10800"
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_MODEL"] = "gpt-5-mini"
os.environ["OPENAI_REQUEST_TIMEOUT_SECONDS"] = "60"
os.environ["OPENAI_REASONING_EFFORT"] = "minimal"
os.environ["OPENAI_VERBOSITY"] = "low"
