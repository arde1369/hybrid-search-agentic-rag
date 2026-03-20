import time


class Timer:
    def __init__(self):
        self._origin = time.perf_counter()
        self._marks = {}

    def start(self, name):
        self._marks[str(name)] = time.perf_counter()
        return self

    def elapsed_ms(self, name):
        start_time = self._marks.get(str(name))
        if start_time is None:
            return 0.0
        return (time.perf_counter() - start_time) * 1000

    def total_ms(self):
        return (time.perf_counter() - self._origin) * 1000

    @staticmethod
    def _format_value(value):
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    @classmethod
    def log(cls, scope, **fields):
        serialized_fields = " ".join(
            f"{key}={cls._format_value(value)}"
            for key, value in fields.items()
        )
        message = f"[TIMING][{scope}]"
        if serialized_fields:
            message = f"{message} {serialized_fields}"
        print(message)
