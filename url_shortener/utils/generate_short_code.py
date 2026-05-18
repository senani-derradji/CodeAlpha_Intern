import random

chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

def generate(original_url: str):
    if isinstance(original_url, str):
        length = len(original_url[:6])
    else :
        length = 6
    return ''.join(random.choice(chars) for _ in range(length))