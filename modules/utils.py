# modules/utils.py

import re

ansi_escape = re.compile(r'\033\[[0-9;]*m')

def strip_ansi(text):
    """Remove ANSI escape codes from a string."""
    return ansi_escape.sub('', text)

def calc_printable_length(text):
    """Calculate the length of the string without ANSI codes."""
    return len(strip_ansi(text))

def pad_string(text, width, align='left'):
    """
    Pad a string to a certain width with alignment.
    :param text: The string to pad.
    :param width: The desired width.
    :param align: 'left', 'right', or 'center'.
    :return: The padded string.
    """
    printable_length = calc_printable_length(text)
    padding = width - printable_length
    if padding < 0:
        # Truncate the text if it's too long
        text = strip_ansi(text)[:width]
        padding = 0
    if align == 'left':
        return text + ' ' * padding
    elif align == 'right':
        return ' ' * padding + text
    elif align == 'center':
        left_padding = padding // 2
        right_padding = padding - left_padding
        return ' ' * left_padding + text + ' ' * right_padding
    else:
        return text  # No padding
