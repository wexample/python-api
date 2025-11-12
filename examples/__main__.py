import sys

from wexample_prompt.example.interactive_executor import InteractiveExecutor

if __name__ == "__main__":
    InteractiveExecutor(
        entrypoint_path=__file__,
        filters=sys.argv[1:],
    ).execute()
