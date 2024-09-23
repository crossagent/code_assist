import functools
import operator
from typing import Sequence, TypedDict, Annotated
from langchain_core.messages import BaseMessage

from langgraph.graph import END, StateGraph, START  # noqa: F401
from langgraph.prebuilt import create_react_agent
from codes.schema.graph_state import AgentState


workflow = StateGraph(AgentState)
workflow.add_node("Researcher", research_node)
workflow.add_node("Coder", code_node)
workflow.add_node("supervisor", supervisor_agent)