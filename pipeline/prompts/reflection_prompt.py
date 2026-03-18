def build_reflection_prompt(question: str, answer: str) -> str:
    return f"""
                    Reflect on the following answer to see if it fully addresses the question.
                    State YES if it is complete and correct, or NO with an explanation.

                Question: {question}

                Answer: {answer}

                    Respond like:
                    Reflection: YES or NO
                    Explanation: ...
                """
