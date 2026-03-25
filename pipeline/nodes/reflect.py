from pipeline.prompts import build_reflection_prompt
import os
from utilities.cache import InMemoryCache, build_cache_key
from utilities.llm_output import llm_result_to_text
from utilities.timer import Timer


def reflect_node(pipeline, state):
    timer = Timer()
    question = str(state.get("effective_question", "") or state.get("question", ""))
    answer = state.get("answer", {})
    thread_id = str(state.get("thread_id", "default_thread") or "default_thread")
    cache_key = build_cache_key(thread_id, question, answer)
    reflection_cache = getattr(pipeline, "_reflection_cache", None)
    cache_hit = False

    if reflection_cache is None:
        reflection_cache = InMemoryCache(max_entries=200)
        pipeline._reflection_cache = reflection_cache

    cached_result = reflection_cache.get(cache_key)
    if cached_result is not None:
        cache_hit = True
        result = cached_result
        print("[REFLECT] Using cached reflection result.")
    else:
        prompt = build_reflection_prompt(question=question, answer=answer)
        def _run_reflection():
            timer.start("llm")
            generated_result = pipeline.llm_agent.invoke(prompt)
            llm_duration_ms = timer.elapsed_ms("llm")
            generated_result = llm_result_to_text(generated_result)
            Timer.log("reflect", llm_ms=llm_duration_ms, cache_hit=False)
            return generated_result

        result = reflection_cache.get_or_set(cache_key, _run_reflection)

    is_complete = "reflection: yes" in result.lower()

    new_attempts = state.get("attempts", 0) + 1
    state["reflection"] = result
    state["revised"] = not is_complete
    state["attempts"] = new_attempts
    Timer.log("reflect", total_ms=timer.total_ms(), cache_hit=cache_hit, attempts=new_attempts)
    return state


def should_continue_refining(state):
    if not state.get("revised", False) or state.get("attempts", 0) >= int(os.getenv("MAX_REFINE_ATTEMPTS", 1)):
        return "end"
    return "refine"
