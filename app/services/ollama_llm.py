from langchain_ollama import OllamaLLM
import pprint

class OllamaLLMService:
    def __init__(self):
        self.llm = OllamaLLM(model="llama3")

    def invoke(self, prompt):
        return self.llm.invoke(prompt)