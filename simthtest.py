from langsmith import Client
from langchain_openai import ChatOpenAI

client = Client()

prompt = client.pull_prompt("joke-generator")
model = ChatOpenAI(model="gpt-4o-mini")

chain = prompt | model
chain.invoke({"topic": "cats"})