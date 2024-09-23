from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
# NOTE: you must use langchain-core >= 0.3 with Pydantic v2
from pydantic import BaseModel, Field
from langchain_core.runnables import Runnable
from codes.schema.robot_api import RobotCode
from typing_extensions import Callable, List, TypedDict, Dict
from codes.schema.graph_state import AgentState
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
    AIMessage
)
import codes.utils.set_env

### OpenAI

def get_code_gen_chain() -> Runnable[str, str]:
    """Get the code generation agent."""

    # Grader prompt
    code_gen_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你的任务是根据自动化用例测试的需求，写出一段python代码，所有机器人的行为，可以通过接口查询""",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    expt_llm = "gpt-4o"
    llm = ChatOpenAI(temperature=0, model=expt_llm)
    code_gen_chain_oai = code_gen_prompt | llm.with_structured_output(RobotCode)

    return code_gen_chain_oai


def invoke_generate_code_node(state:AgentState) -> List[BaseMessage]:

    concatenated_content = state["messages"][-1]

    code_gen_chain_oai = get_code_gen_chain()

    solution = code_gen_chain_oai.invoke({"context":concatenated_content,"messages":state["messages"]})

    return {"messages": [HumanMessage(content=solution.code, name="CodeGenerate")]}

if __name__ == "__main__":

    agent_state = AgentState(messages=[
        HumanMessage(content="跑动前方5米，装备狙击枪，更换.56子弹"),
        HumanMessage(content="从机器人接口查询相关的接口信息"),
        AIMessage(content='[{"function_name": "move", "args": ["self", "yaw", "run_num", "direction"]}, {"function_name": "move_pos", "args": ["self", "x", "y", "z", "run_num", "direction"]}, {"function_name": "move_pos", "args": ["self", "x", "y", "z", "run_num", "direction"]}, {"function_name": "switch_weaponlights", "args": ["self", "enable", "accessory_id"]}, {"function_name": "fire_to_robot", "args": ["self", "role_id"]}, {"function_name": "fire_to_robot", "args": ["self", "role_id"]}, {"function_name": "reload_ammo", "args": ["self", "ammo_id"]}, {"function_name": "switch_weaponlights", "args": ["self", "enable", "accessory_id"]}, {"function_name": "switch_weaponlights", "args": ["self", "enable", "accessory_id"]}]', name='ApiSearcher')
        ])
    
    result = invoke_generate_code_node(agent_state)

    print(result)