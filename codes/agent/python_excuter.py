from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from typing_extensions import Callable, List, TypedDict, Dict
from codes.schema.graph_state import AgentState
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from codes.utils.agent_node_creater import agent_node
# This executes code locally, which can be unsafe
python_repl_tool = PythonREPLTool()

from langgraph.prebuilt import create_react_agent
import functools

def get_python_excuter_agent():
    # NOTE: THIS PERFORMS ARBITRARY CODE EXECUTION. PROCEED WITH CAUTION

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    system_prompt = (
        """你是一个python执行器，你的任务是执行python代码，并返回执行结果。
    """
    )

    code_agent = create_react_agent(llm, tools=[python_repl_tool], state_modifier=system_prompt, interrupt_after=["tools"])

    return code_agent

def get_excuter_node() -> Callable[[AgentState], Dict[str, List[BaseMessage]]]:
    code_agent = get_python_excuter_agent()

    code_node = functools.partial(agent_node, agent=code_agent, name="Coder")

    return code_node

if __name__ == "__main__":

    agent_state = AgentState(messages=[HumanMessage(content="a = 5+7")])

    code_node = get_excuter_node()

    output = code_node(agent_state)

    print(output)