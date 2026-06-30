class FilterError(Exception):
    """高级筛选条件非法（未知字段、不支持的操作符、值格式错误等）。"""
    pass
