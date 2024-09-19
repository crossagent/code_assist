#tools as a search tool， search the api and return the result

from langchain_core.tools import tool
from codes.schema.robot_api import RobotActionDescription
from typing import Annotated, List

@tool
def robot_action(action: Annotated[str, ""] ) -> RobotActionDescription:
    return RobotActionDescription(
        function_name="robot_action",
        parameters={}
    )    