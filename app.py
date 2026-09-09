from typing import TypedDict, List, Optional
from dotenv import load_dotenv

from fastapi import FastAPI
from pydantic import BaseModel

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
import google.generativeai as genai

# Load environment variables (useful for local testing with a .env file)
# Load environment variables
load_dotenv()

# ==========================================
# 1. LLM INITIALIZATION
# ==========================================
api_key = os.getenv('GEMINI_API_KEY')

if not api_key:
    print("Error: GEMINI_API_KEY environment variable not found. Please set it in Render.")
    sys.exit(1)

genai.configure(api_key=api_key)
print("API Key configured successfully.")
if api_key:
    genai.configure(api_key=api_key)

# Initialize the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview", # Note: Ensure this model version is currently active on your GCP/AI Studio account
    model="gemini-3.1-flash-lite-preview", 
google_api_key=api_key
)

@@ -37,7 +35,6 @@
# ==========================================
class CrewState(TypedDict):
messages: List[BaseMessage]
    next_step: Optional[str]
code: Optional[str]
report: Optional[str]

@@ -80,38 +77,21 @@ def generate_test_cases(task_description: str) -> str:
# ==========================================
# 4. GRAPH NODES
# ==========================================
def task_input_node(state: CrewState):
    print("\n" + "="*50)
    print("--- NEW TASK INITIALIZATION ---")
    user_task = input("Enter the coding task (or type 'exit' to quit): ").strip()

    if user_task.lower() == 'exit':
        return {"next_step": "exit"}

    return {
        "messages": [HumanMessage(content=user_task)],
        "next_step": "developer"
    }

def real_time_developer(state: CrewState):
    print("\n[Developer] Writing dynamic code using LLM...")
task = state['messages'][-1].content
dev_prompt = f"Write a clean Python script to solve this: {task}. Only return the code, no explanation or markdown formatting."

response = llm.invoke(dev_prompt)

    # Safely parse Gemini's content format
content = response.content
if isinstance(content, list):
code_str = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
else:
code_str = str(content)

    print(code_str)
return {"code": code_str}

def real_time_tester(state: CrewState):
    print("\n[Tester] Generating dynamic tests and executing code...")
task = state['messages'][-1].content

# Generate tests
@@ -129,66 +109,42 @@ def real_time_tester(state: CrewState):
report = f"### EXECUTION OUTPUT:\n{execution_result}\n\n### TEST SCENARIOS EVALUATED:\n{cases_str}"
return {"report": report}

def manager_decision_node(state: CrewState):
    print("\n" + "="*50)
    print("--- MANAGER DASHBOARD : TEST REPORT ---")
    print(state.get('report', 'No report available.'))
    print("="*50)

    user_input = input("\nCommand (store / another): ").lower().strip()

    if user_input == 'store':
        return {"next_step": "archiver"}
    else:
        return {"next_step": "task_input"}

def archiver_node(state: CrewState):
    print("\n[Archiver] Task stored successfully. Closing workflow.")
    return {"next_step": "exit"}

# ==========================================
# 5. GRAPH CONSTRUCTION & ROUTING
# ==========================================
rt_workflow = StateGraph(CrewState)

rt_workflow.add_node("task_input", task_input_node)
rt_workflow.add_node("developer", real_time_developer)
rt_workflow.add_node("tester", real_time_tester)
rt_workflow.add_node("manager_decision", manager_decision_node)
rt_workflow.add_node("archiver", archiver_node)

rt_workflow.add_edge(START, "task_input")

def route_from_input(state):
    if state.get('next_step') == "exit":
        return END
    return "developer"

rt_workflow.add_conditional_edges("task_input", route_from_input)

# Sequential flow
# Sequential flow for the API
rt_workflow.add_edge(START, "developer")
rt_workflow.add_edge("developer", "tester")
rt_workflow.add_edge("tester", "manager_decision")

def route_from_decision(state):
    if state.get('next_step') == "archiver":
        return "archiver"
    return "task_input"

rt_workflow.add_conditional_edges("manager_decision", route_from_decision)
rt_workflow.add_edge("archiver", END)
rt_workflow.add_edge("tester", END)

rt_app = rt_workflow.compile()
print("Interactive pipeline compiled and ready for live execution.")

# ==========================================
# 6. EXECUTION LOOP
# 6. FASTAPI WEB SERVER SETUP
# ==========================================
if __name__ == "__main__":
app = FastAPI(title="LangGraph AI Crew")

class TaskRequest(BaseModel):
    task: str

@app.get("/")
def home():
    return {"message": "API is running. Send a POST request to /run with a JSON body containing your 'task'."}

@app.post("/run")
def run_task(req: TaskRequest):
try:
        # Start the application with an empty state
        rt_app.invoke({"messages": []}, config={"recursion_limit": 50})
    except KeyboardInterrupt:
        print("\nStopped by user.")
        # Pass the incoming task directly to the LangGraph workflow
        result = rt_app.invoke({"messages": [HumanMessage(content=req.task)]})
        return {
            "status": "success",
            "generated_code": result.get("code"),
            "test_report": result.get("report")
        }
except Exception as e:
        print(f"\nAn error occurred: {e}")
        return {"status": "error", "message": str(e)}
