def first_large(xs: list[int]) -> int:
    total = 0
    for x in xs:
        if x > 100:
            return x
        total = total + x
    return total
