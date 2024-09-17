# Import neccasary packages
from langchain.prompts import ChatPromptTemplate
from datetime import datetime 
from pytz import timezone
from support_files.tool_execution import customer_existence_verification, customer_lead_creation
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import ToolMessage


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


# Define timezone
ist_timezone = timezone("Asia/Kolkata")
model = ChatGroq(model="llama3-70b-8192",temperature=0)


lead_agent_prompt_template = ChatPromptTemplate.from_messages(
    messages=[
        ("system",
         ("You are a specialized assistant for handling lead creation, updation, and deletion. "
          "The primary assistant delegates work to you whenever the user needs help with a lead creation, updation, or deletion. "
          "Check whether the customer exists or not and get human feedback before proceeding to lead creation, lead updation, or lead deletion process. "
          "You should always provide the reply to the customer in the way of a concise, detailed, and informative message and don't use form like structure. "
          "If you need more information or the customer changes their mind, escalate the task back to the main assistant. "
          "When searching, be persistent. Expand your query bounds if the first search returns no results. "
          "Remember that lead creation, updating, or deletion is not completed until after the relevant tool has been successfully used."
          "\nCurrent time: {time}"
          "\n\nIf the user needs help, and none of your tools are appropriate for it, then 'CompleteOrEscalate' the dialog to the host assistant. "
          "Do not waste the user\'s time. Do not make up invalid tools or functions."
          "\n\nSome examples for which you should CompleteOrEscalate:\n"
          "- 'nevermind, I think I'll manage the lead separately'\n"
          "- 'I need to confirm the customer's vehicle model before creating the lead'\n"
          "- 'Oh wait, I haven't updated the lead's contact details, I'll do that first'\n"
          "- 'Lead successfully deleted!'")
        ),
        ("placeholder", "{messages}")
    ]
).partial(time=datetime.now(ist_timezone).isoformat())

safe_tool = [customer_existence_verification]

sensitive_tool = [customer_lead_creation]

lead_agent_tool = safe_tool+sensitive_tool

lead_assistant_runnable = lead_agent_prompt_template | model.bind_tools(lead_agent_tool + [CompleteOrEscalate])

