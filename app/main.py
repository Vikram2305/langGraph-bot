# import neccasary packages
from datetime import datetime
from pytz import timezone
from typing import TypedDict, Annotated
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import StateGraph, START, END
from typing import Callable
from langchain_core.messages import ToolMessage
from langgraph.graph.message import AnyMessage, add_messages
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import Runnable, RunnableConfig
from support_files.tool_execution import *
from support_files.lead_agent import lead_assistant_runnable, lead_agent_tool,safe_tool, sensitive_tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition
ist_timezone = timezone("Asia/Kolkata")
from dotenv import load_dotenv
load_dotenv()
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
import os

LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY= os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT="LangGraph-Chatbot"

def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                "lead_existance_verification",
                "lead_creation",
            ]
        ],
        update_dialog_stack,
    ]
class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}

class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str

    class Config:
        schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "reason": "I need to search the emails for more information.",
            },
        }

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)

class Lead_assistant(BaseModel):
    """Transfer work to a specialized assistant to handle the lead relevant details."""

    location: str = Field(
        description="The location where the user wants create or udate or delete the lead."
    )
    name: str = Field(description="Name of the customer.")
    phone: str = Field(description="Phone number of the customer.")
    email: str = Field(description="Email of the customer.")
    civilID: str = Field(description="Civil ID of the customer.")

    request: str = Field(
        description="Any additional information or requests from the user regarding the create or udate or delete the lead."
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "Chandru",
                "phone": "+91 8124832683",
                "email": "chandruganeshan@gmail.com",
                "civilID": "986534567893",
            }
        }


def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        print("this is tool call id", tool_call_id)
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, other other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


model = ChatGroq(model="llama3-70b-8192",temperature=1)

primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful customer support assistant for Automotive Industry."
            "Your primary role is search leads, customer details, test drive details and other customer required deatils."
            "If the customer wants to create or update or delete the lead, book test drive, create a quotation, "
            "delegate the task to appropriate specialized assistants by invoking corresponding tools. You are not able to make these type of changes yourself"
            "Only the specialized assistants are given permission to do this for the user."
            "The user is not aware of the different specialized assistants, so do not mention them; just quietly delegate through function calls. "
            "Provide detailed information to the customer, and always double-check the database before concluding that information is unavailable. "
            "When searching, be persistent. Expand your query bounds if the first search returns no results."
            "If a search comes up empty, expand your search before giving up."
            "\nCurrent time: {time}."
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now(ist_timezone).isoformat())

# primary_assistant_tools = [customer_existence_verification]
primary_assistant_runnable = primary_assistant_prompt | model.bind_tools([Lead_assistant])
def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    print(messages)
    return {
        "dialog_state": "pop",
        "messages": messages,
    }

# Compile graph
builder = StateGraph(State)

builder.add_node("enter_lead_assistant",create_entry_node("Lead Assistant", "lead_agent"))
builder.add_node("lead_agent", Assistant(lead_assistant_runnable))
builder.add_edge("enter_lead_assistant", "lead_agent")

builder.add_node(
    "lead_assistant_safe_tools",
    create_tool_node_with_fallback(safe_tool)
)

builder.add_node(
    "lead_assistant_sensitive_tools",
    create_tool_node_with_fallback(sensitive_tool)
)

builder.add_node("primary_assistant", Assistant(primary_assistant_runnable))
builder.add_edge(START, "primary_assistant")
# builder.add_node("primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools))
builder.add_node("leave_skill", pop_dialog_state)
builder.add_edge("leave_skill", "primary_assistant")
# builder.add_edge("primary_assistant", "enter_lead_assistant")

def route_lead_assistant(
    state: State,
) -> Literal[
    "lead_assistant_safe_tools",
    "lead_assistant_sensitive_tools",
    "leave_skill",
    "__end__",
]:
    route = tools_condition(state)
    print("This is the route",route)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    
    if did_cancel:
        print("This is the tool calls",tool_calls)
        print("this is the name",CompleteOrEscalate.__name__)
        return "leave_skill"
    
    safe_toolnames = [t.name for t in safe_tool]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        print("This is the safe tool names",safe_toolnames)
        return "lead_assistant_safe_tools"
    
    sensitive_toolnames = [t.name for t in sensitive_tool]
    if all(tc["name"] in sensitive_toolnames for tc in tool_calls):
        print("This is the sensitive tool names",sensitive_toolnames)
        return "lead_assistant_sensitive_tools"

    return END


######################################################################################

def route_primary_assistant(
    state: State,
) -> Literal[
    "primary_assistant",
    "enter_lead_assistant",
    "__end__",
]:
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        if tool_calls[0]["name"] == Lead_assistant.__name__:
            return "enter_lead_assistant"
        return "primary_assistant"
    raise ValueError("Invalid route")


# The assistant can route to one of the delegated assistants,
# directly use a tool, or directly respond to the user
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    {
        "enter_lead_assistant": "enter_lead_assistant",
        "primary_assistant": "primary_assistant",
        END: END,
    },
)
# builder.add_edge("primary_assistant_tools", "primary_assistant")

def route_to_workflow(
    state: State,
) -> Literal[
    "primary_assistant",
    "lead_agent",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]


# builder.add_conditional_edges("fetch_user_info", route_to_workflow)

builder.add_edge("lead_assistant_safe_tools", "lead_agent")
builder.add_edge("lead_assistant_sensitive_tools", "lead_agent")
builder.add_conditional_edges("lead_agent",route_lead_assistant)

# Compile graph
memory = MemorySaver()
part_4_graph = builder.compile(checkpointer=memory,interrupt_before=["lead_assistant_sensitive_tools"]) #,

part_4_graph.get_graph(xray=True).draw_mermaid_png(output_file_path="part_4_graph.png")

config = {
    "configurable": {
        "thread_id": 1,
    }
}

_printed = set()
while True:
    print(State["messages"])
    question = input("Ask question: ")
    events = part_4_graph.stream(
        {"messages": ("user", question)}, config, stream_mode="values"
    )
    for event in events:
        _print_event(event, _printed)
        # print(event)