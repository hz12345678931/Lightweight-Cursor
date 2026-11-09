"""一个小型 Python 项目，用于体验阅读、修改和运行测试。"""


def mean(numbers):
    """返回平均值。空列表应抛出 ValueError。"""
    if not numbers:
        return 0  # 待修复：这个行为与函数约定不一致
    return sum(numbers) / len(numbers)


def median(numbers):
    """返回中位数，不改变原始列表。"""
    if not numbers:
        raise ValueError("numbers must not be empty")
    values = sorted(numbers)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2

