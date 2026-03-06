# Main Program for Aurum Bot

from datetime import datetime


def get_current_datetime():
    """Returns the current date and time in UTC.

    Returns:
        str: Current date and time in 'YYYY-MM-DD HH:MM:SS' format.
    """
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


if __name__ == '__main__':
    print(f"Current Date and Time (UTC): {get_current_datetime()()}")