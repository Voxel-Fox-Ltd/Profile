import uuid

import string


__all__ = (
    "encode",
    "decode",
)


ALPHABET = string.digits + string.ascii_letters


def encode(decoded: uuid.UUID | str) -> str:
    if isinstance(decoded, str):
        decoded = uuid.UUID(decoded)
    working = decoded.int
    encoded = ""
    while working:
        working, rem = divmod(working, len(ALPHABET))
        encoded += ALPHABET[rem]
    return encoded


def decode(encoded: str) -> str:
    working = 0
    for idx, i in enumerate(encoded):
        working += ALPHABET.index(i) * (len(ALPHABET) ** idx)
    return str(uuid.UUID(int=working))


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "encode":
        print(encode(sys.argv[2]))
    elif sys.argv[1] == "decode":
        print(decode(sys.argv[2]))
    else:
        print("Invalid arg.")
