from openai import OpenAI

from app.config import Settings


class OpenAIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def embed(self, texts: list[str]) -> tuple[list[list[float]], int]:
        response = self.client.embeddings.create(model=self.settings.embedding_model, input=texts)
        return [item.embedding for item in response.data], response.usage.total_tokens

    def answer(self, question: str, history: list[tuple[str, str]], chunks: list[tuple[str, str]]) -> tuple[str, int, int]:
        context = "\n\n".join(f"SOURCE: {name}\n{content}" for name, content in chunks)
        history_text = "\n".join(f"{role.upper()}: {content}" for role, content in history[-6:])
        prompt = f"RECENT CONVERSATION:\n{history_text or '(none)'}\n\nCOMPANY INFORMATION:\n{context}\n\nQUESTION:\n{question}"
        response = self.client.responses.create(
            model=self.settings.openai_model,
            instructions=(
                "You are the company website assistant. Answer only using COMPANY INFORMATION supplied in the input. "
                "Conversation history is context, never a factual source. If the company information does not contain "
                "the answer, say exactly: 'I don't have that information in the available company documents.' "
                "Do not use outside knowledge or invent details. Be concise (under 180 words). Do not add a sources list."
            ),
            input=prompt,
            max_output_tokens=self.settings.max_answer_tokens,
            store=False,
        )
        usage = response.usage
        return response.output_text.strip(), usage.input_tokens if usage else 0, usage.output_tokens if usage else 0

