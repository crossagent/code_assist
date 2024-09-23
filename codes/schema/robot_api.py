from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from typing_extensions import Annotated, TypedDict, Optional, List

# 定义工具函数的描述数据结构
class RobotActionDescription(TypedDict):
    function_name: Annotated[str, "This is the name of the function"]
    args: Annotated[Optional[dict], "This is a dictionary containing the arguments for the function"]


# Data model
class RobotCode(BaseModel):
    """Schema for code solutions to questions about LCEL."""

    prefix: str = Field(description="Description of the problem and approach")
    imports: str = Field(description="Code block import statements")
    code: str = Field(description="Code block not including import statements")
