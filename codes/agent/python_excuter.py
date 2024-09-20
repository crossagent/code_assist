from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI

# This executes code locally, which can be unsafe
python_repl_tool = PythonREPLTool()

from langchain.agents import create_react_agent
import functools
from typing import Literal

def get_python_excuter_agent():
    # NOTE: THIS PERFORMS ARBITRARY CODE EXECUTION. PROCEED WITH CAUTION

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    code_agent = create_react_agent(llm, tools=[python_repl_tool])
    code_node = functools.partial(agent_node, agent=code_agent, name="Coder")