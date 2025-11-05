from langchain_ollama.chat_models import ChatOllama
from langchain_core.messages import HumanMessage

class OllamaLLMChatService:
    def __init__(self):
        self.chat_model = ChatOllama(model="llama3")

    def invoke(self, prompt: str):
        prompts = [HumanMessage(prompt)]
        response =  self.chat_model.invoke(prompts)
        return response.content