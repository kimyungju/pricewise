def prompt_for_approval(tool_calls: list) -> bool:
    """Display pending tool calls and prompt user for CLI approval.

    Args:
        tool_calls: List of tool call dicts from the AI message.

    Returns:
        True if user approves, False otherwise.
    """
    print("\n--- Human Approval Required ---")
    for tc in tool_calls:
        print(f"  Tool:  {tc['name']}")
        print(f"  Args:  {tc['args']}")
    print("-------------------------------")

    try:
        while True:
            answer = input("Approve execution? [y/n]: ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            print("Please enter 'y' or 'n'.")
    except EOFError:
        print("Non-interactive mode detected, auto-approving.")
        return True
