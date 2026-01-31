
def estimate_tokens(text: str) -> int:
    """
    Консервативная эвристика токенов.
    Для JSON / tools / system prompt считаем ~2 символа на токен.
    """
    if not text:
        return 0
    return int(len(text) / 2.0) + 5
