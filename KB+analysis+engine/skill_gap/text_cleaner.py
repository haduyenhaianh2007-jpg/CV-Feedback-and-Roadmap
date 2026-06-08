"""
Text Cleaner - Utility để làm sạch output từ ollama CLI
"""
import re

# ANSI escape sequences (terminal colors, cursor movements)
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Control characters (EXCEPT newline, tab, carriage return)
# \x00-\x08: NULL to BACKSPACE
# \x0B-\x0C: VT and FF
# \x0E-\x1F: SO to US
# \x7F: DEL
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')

# Braille spinner characters (ollama loading animation)
SPINNER_CHARS = re.compile(r'[⠁-⣿]')

# Cursor positioning codes like [1G, [2K
CURSOR_CODES = re.compile(r'\[[0-9]*[GKDH]')

# Terminal wrap artifact: ký tự cuối dòng được lặp lại ở đầu dòng tiếp theo
# Example: "V\nVới" → "V\nVới" (chữ V bị lặp)
# Example: "tr\ntrong" → "tr\ntrong" (tr bị lặp)
# Example: "khoảng\nkhoảng" → "khoảng\nkhoảng" (từ khoảng bị lặp)
WRAP_ARTIFACT = re.compile(r'([a-zA-ZÀ-ỹ]{1,10})\n\1')

def clean_ollama_output(text: str) -> str:
    """
    Làm sạch output từ ollama CLI:
    - Strip ANSI escape codes
    - Strip control chars (giữ lại \n, \t, \r)
    - Strip spinner animation
    - Fix terminal wrap artifacts (double chars)
    - Collapse multiple spaces/newlines
    """
    # Strip ANSI và control chars
    text = ANSI_ESCAPE.sub('', text)
    text = CONTROL_CHARS.sub('', text)
    text = SPINNER_CHARS.sub('', text)
    text = CURSOR_CODES.sub('', text)

    # Fix wrap artifacts (ký tự cuối dòng lặp lại ở đầu dòng tiếp theo)
    # Thay thế "char\nchar" bằng "char\n" (giữ lại dòng mới, xóa ký tự lặp)
    text = WRAP_ARTIFACT.sub(r'\1\n', text)

    # Collapse multiple spaces (but keep newlines)
    text = re.sub(r'[^\S\n]{2,}', ' ', text)

    # Collapse multiple newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

if __name__ == "__main__":
    # Test
    with open('real_cv_feedback_v2.md', 'r', encoding='utf-8') as f:
        raw = f.read()

    clean = clean_ollama_output(raw)

    with open('real_cv_feedback_v5_clean.md', 'w', encoding='utf-8') as f:
        f.write(clean)

    print(f'Original: {len(raw)} chars, {raw.count(chr(10))} newlines')
    print(f'Cleaned: {len(clean)} chars, {clean.count(chr(10))} newlines')
