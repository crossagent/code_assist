#tools as a search tool， search the api and return the result

from langchain_core.tools import InjectedToolArg, tool
from codes.schema.robot_api import RobotActionDescription
from typing import Annotated, List
from langchain_community.vectorstores import FAISS
from codes.utils.set_env import api_db_path
from langchain_openai import OpenAIEmbeddings

vector_store = FAISS.load_local(api_db_path, embeddings = OpenAIEmbeddings(model = "text-embedding-3-large"), allow_dangerous_deserialization=True)

@tool
def robot_action(action: Annotated[str, "actions list robot need to search interface"],
                 max_k: Annotated[int, InjectedToolArg] = 2) -> List[RobotActionDescription]:
    """
    This tool allows the robot to perform an action based on the input string.
    """
    results = []

    search_results = vector_store.similarity_search_with_score(query=action, k=max_k, filter={"module_name": "multiplayer_op"})
    
    # 假设 search_results 是一个列表，其中每个元素包含一个结果
    for result, score in search_results:  # 遍历所有搜索结果
        if score < 5:
            print(f"found result:{result.metadata['function_name']}, score:{score}")

            # 创建 RobotActionDescription 对象并添加到结果列表
            description = RobotActionDescription(
                function_name=result.metadata["function_name"],
                args=result.metadata["args"],
            )
            results.append(description)
        else:
            # 如果没有找到结果，返回一个空的描述
            description = RobotActionDescription(
                function_name="No result found",
                args=[]
            )
    results.append(description)

    return results


# 确保main函数作为程序入口被调用
if __name__ == "__main__":
    # Let's inspect some of the attributes associated with the tool.
    print(robot_action.name)
    print(robot_action.description)
    print(robot_action.args)
    print(robot_action.get_input_schema().schema())
    print(robot_action.tool_call_schema.schema())

    #print(robot_action.invoke({"action": "跑动", "max_k": 3}))
    robot_action.invoke({"action": "火星探测", "max_k": 3})
    #robot_action.invoke({"action": "更换子弹", "max_k": 3})