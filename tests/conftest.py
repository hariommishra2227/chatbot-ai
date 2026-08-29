import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://chatbot:test@localhost:5432/chatbot_test")
os.environ["ADMIN_API_KEY"] = "test-admin-api-key-at-least-24"
os.environ.setdefault("AI_PROVIDER_MODE", "mock")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "1024")
os.environ.setdefault("BEDROCK_EMBEDDING_DIMENSIONS", "1024")
