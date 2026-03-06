
def estimate_tokens(text: str) -> int:
    """
    Консервативная эвристика токенов с запасом.
    Для JSON / tools / system prompt считаем ~2 символа на токен.
    Дополнительный запас +15 для учета platform differences.
    """
    if not text:
        return 0
    return int(len(text) / 2.0) + 15
