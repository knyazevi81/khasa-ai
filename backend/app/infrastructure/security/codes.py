import secrets


def generate_numeric_code(length: int = 6) -> str:
    """
    Криптографически стойкий числовой код фиксированной длины.
    Используется для email-верификации.
    """
    if length < 4 or length > 10:
        raise ValueError("length must be in [4, 10]")
    # Один секрет-байт → цифра, итерация до набора нужной длины
    digits: list[str] = []
    while len(digits) < length:
        b = secrets.randbelow(10)
        digits.append(str(b))
    return "".join(digits)
