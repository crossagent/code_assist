from langchain.agents import create_tool_calling_agent

agent = create_tool_calling_agent(llm, tools, prompt)