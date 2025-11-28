from langchain_ollama.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
from app.services.system_message_store import SystemMessageStore


class OllamaLLMChatService:
    def __init__(self):
        self.chat_model = ChatOllama(model="llama3")
        self.system_message_store = SystemMessageStore()
        self.system_msg = self.system_message_store.render_system_message(
            "engineering.no_hallucinations.concise",
            knowledge_cutoff="2025-06-01",  # Required cutoff date
            today="2025-11-10",  # Current date
            timezone="America/Toronto",  # Timezone for date calculations
            jurisdiction="SOX/PCI",  # Compliance requirement
            max_words=500
        )

    def invoke(self, prompt: str):
        prompts = [self.system_msg, HumanMessage(prompt)]
        response = self.chat_model.invoke(prompts)
        return response.content
