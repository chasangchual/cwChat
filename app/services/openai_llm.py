from langchain_openai.llms import OpenAI
import pprint

model = OpenAI(model="gpt-5-mini")
out = model.invoke("Say this is a test")

pprint.pprint(out)