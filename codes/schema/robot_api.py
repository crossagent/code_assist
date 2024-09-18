from pydantic import BaseModel

# 定义工具函数的描述数据结构
class RobotActionDescription(BaseModel):
    function_name: str
    args: dict