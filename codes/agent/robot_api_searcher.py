from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from codes.tools.robot_action_tool import robot_action
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from typing_extensions import Callable, List, TypedDict, Dict
import codes.utils.set_env
from langgraph.graph.graph import CompiledGraph
import json
import functools
from codes.schema.graph_state import AgentState

def get_api_searcher_agent() -> CompiledGraph:
    """
    创建一个接口查询助手
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    system_prompt = (
        """你是一个接口查询助手，需要根据需要机器人执行的行为，查找对应的api接口用于后续的代码编写参考。
    """
    )

    api_agent = create_react_agent(llm, tools = [robot_action], state_modifier=system_prompt)

    return api_agent

def invoke_api_search_agent_node(state, agent, name):
    """
    这个函数实际上是把agent做的事情，最终用HumanMessage的形式返回，实际上是做了一个最终总结的工作
    """
    msg = agent.invoke(state)

    tool_messages_content = []

    # 遍历 msg["messages"]
    for message in msg["messages"]:
        # 检查消息类型是否为 ToolMessage
        if message.type == "tool":
            content_str = message.content
            try:
                # 将 content 字符串还原为 Python 对象
                content = json.loads(content_str)
                # 确保 content 是 List[RobotActionDescription] 类型
                if isinstance(content, list):
                    tool_messages_content.extend(content)
            except json.JSONDecodeError:
                print(f"Failed to decode JSON for message: {message}")

    return {"messages": [HumanMessage(content={f"Information about potentially used API functions:{json.dumps(tool_messages_content)}"}, name=name)]}

def get_api_searcher_node() -> Callable[[AgentState], Dict[str, List[BaseMessage]]]:
    agent = get_api_searcher_agent()

    api_search_node = functools.partial(invoke_api_search_agent_node, agent=agent, name="ApiSearcher")

    return api_search_node

# 确保main函数作为程序入口被调用
if __name__ == "__main__":

    agent_state = AgentState(messages=[HumanMessage(content="跑动前方5米，装备狙击枪，更换.56子弹")])

    node = get_api_searcher_node()

    output = node(agent_state)

    print(output)
    