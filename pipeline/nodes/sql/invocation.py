from pipeline.nodes.sql.generation import repair_sql_query_with_schema
from pipeline.nodes.sql.validation import is_schema_resolution_error, validate_sql_schema_alignment
from pipeline.nodes.vector import resolve_vector_collection_name


def get_tool_by_name(pipeline, tool_name):
    for tool in pipeline.dao_tools:
        current_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
        if current_name == tool_name:
            return tool
    return None


def invoke_tool(pipeline, route):
    tool_name = route.get("tool_name")
    tool_input = route.get("tool_input", {})

    if tool_name == "chroma_db_retriever" and isinstance(tool_input, dict):
        collection_name = str(tool_input.get("collection_name", "") or "").strip()
        if not collection_name:
            inferred_collection = resolve_vector_collection_name(pipeline, route.get("sub_query", ""))
            if inferred_collection:
                tool_input = dict(tool_input)
                tool_input["collection_name"] = inferred_collection
                route["tool_input"] = tool_input
                print(
                    "[INVOCATION] Missing collection_name for chroma_db_retriever; "
                    f"auto-filled with '{inferred_collection}'."
                )

    if route.get("route") == "sql":
        status = str(route.get("validation_status", ""))
        if status.startswith("blocked_invalid_sql") or status.startswith("regeneration_error"):
            raise ValueError(f"Blocked invalid SQL before execution: {status}")

        if isinstance(tool_input, dict) and isinstance(tool_input.get("query"), str):
            live_schema = pipeline.sql_dao.get_full_schema()
            is_valid, validation_error = validate_sql_schema_alignment(tool_input.get("query", ""), live_schema)
            if not is_valid:
                repaired_sql = repair_sql_query_with_schema(
                    pipeline,
                    sub_query=route.get("sub_query", ""),
                    broken_sql=tool_input.get("query", ""),
                    error_message=validation_error,
                )
                if repaired_sql:
                    is_repaired_valid, repaired_error = validate_sql_schema_alignment(repaired_sql, live_schema)
                    if is_repaired_valid:
                        tool_input = dict(tool_input)
                        tool_input["query"] = repaired_sql
                        route["tool_input"] = tool_input
                    else:
                        raise ValueError(f"Blocked invalid SQL before execution: {repaired_error}")
                else:
                    raise ValueError(f"Blocked invalid SQL before execution: {validation_error}")

    tool = get_tool_by_name(pipeline, tool_name)
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' was not found.")

    if hasattr(tool, "invoke"):
        try:
            return tool.invoke(tool_input)
        except Exception as invoke_error:
            if (
                tool_name == "select"
                and isinstance(tool_input, dict)
                and isinstance(tool_input.get("query"), str)
                and is_schema_resolution_error(str(invoke_error))
            ):
                repaired_sql = repair_sql_query_with_schema(
                    pipeline,
                    sub_query=route.get("sub_query", ""),
                    broken_sql=tool_input.get("query", ""),
                    error_message=str(invoke_error),
                )
                if repaired_sql:
                    repaired_input = dict(tool_input)
                    repaired_input["query"] = repaired_sql
                    route["tool_input"] = repaired_input
                    return tool.invoke(repaired_input)

            if tool_name == "select":
                raise

            # Backward-compatible fallback only for single-argument query tools.
            if (
                isinstance(tool_input, dict)
                and "query" in tool_input
                and tool_name != "chroma_db_retriever"
            ):
                return tool.invoke(tool_input["query"])
            raise

    if isinstance(tool_input, dict):
        return tool(**tool_input)

    return tool(tool_input)
