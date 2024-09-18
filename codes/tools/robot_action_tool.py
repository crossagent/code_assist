#tools as a search tool， search the api and return the result

from langchain_core import tools
from codes.schema.robot_api import RobotActionDescription

@tools
def robot_action(action: str) -> RobotActionDescription:
    return RobotActionDescription(
        function_name="robot_action",
        parameters={"action": action}
    )    