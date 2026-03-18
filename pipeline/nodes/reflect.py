from pipeline.prompts import build_reflection_prompt


def reflect_node(pipeline, state):
    question = state.get("question", "")
    answer = state.get("answer", {})
    prompt = build_reflection_prompt(question=question, answer=answer)
    result = pipeline.llm_agent.invoke(prompt)
    if not isinstance(result, str):
        result = str(result)
    is_complete = "reflection: yes" in result.lower()

    new_attempts = state.get("attempts", 0) + 1
    state["reflection"] = result
    state["revised"] = not is_complete
    state["attempts"] = new_attempts
    return state


def should_continue_refining(state):
    if not state.get("revised", False) or state.get("attempts", 0) >= 2:
        return "end"
    return "refine"
