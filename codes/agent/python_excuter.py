from langchain_experimental.tools import PythonREPLTool
# This executes code locally, which can be unsafe
python_repl_tool = PythonREPLTool()

from langchain.agents import create_react_agent
import functools
from typing import Literal

# NOTE: THIS PERFORMS ARBITRARY CODE EXECUTION. PROCEED WITH CAUTION
code_agent = create_react_agent(llm, tools=[python_repl_tool])
code_node = functools.partial(agent_node, agent=code_agent, name="Coder")