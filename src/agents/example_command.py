"""
LangGraph 1.0 Example - New Command Pattern

This demonstrates the new approach in LangGraph 1.0:
- Command objects for routing
- Cleaner node definitions
- Better type safety
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from typing_extensions import TypedDict


# Define state
class State(TypedDict):
    """Agent state."""
    count: int
    message: str


# Define nodes using the new pattern
def start_node(state: State) -> Command[Literal["process", "finish"]]:
    """
    Entry node - returns Command to route to next node.

    The Command object specifies:
    - goto: next node name
    - update: state updates
    """
    count = state.get("count", 0) + 1

    if count < 3:
        # Continue processing
        return Command(
            goto="process",
            update={"count": count, "message": f"Starting iteration {count}"}
        )
    else:
        # Finished
        return Command(
            goto="finish",
            update={"count": count, "message": "Processing complete"}
        )


def process_node(state: State) -> Command[Literal["start"]]:
    """Process node - does work and routes back."""
    return Command(
        goto="start",
        update={"message": f"Processed {state['count']} items"}
    )


def finish_node(state: State) -> Command:
    """Final node - ends the graph."""
    return Command(goto=END, update={"message": f"Finished with {state['count']} iterations"})


# Build graph
def build_graph() -> StateGraph:
    """Build graph using LangGraph 1.0 Command pattern."""

    # Create graph
    graph = StateGraph(State)

    # Add nodes
    graph.add_node("start", start_node)
    graph.add_node("process", process_node)
    graph.add_node("finish", finish_node)

    # Set entry point
    graph.add_edge(START, "start")

    # Nodes use Command to route themselves - no add_edge needed!
    # The Command object's 'goto' field handles routing

    return graph


# Run example
if __name__ == "__main__":
    # Build and compile
    graph = build_graph()
    app = graph.compile()

    # Run
    print("\n🚀 Running LangGraph 1.0 with Command pattern...\n")

    result = app.invoke({"count": 0, "message": ""})

    print("✅ Final state:")
    print(f"   Count: {result['count']}")
    print(f"   Message: {result['message']}\n")
