"""CD2 gRPC 错误信息提取工具"""


def grpc_error_details(e: Exception) -> str:
    """提取 gRPC 错误的可读信息。

    gRPC 的 _InactiveRpcError.details 是方法对象（真值），直接 getattr 会把
    未调用的方法对象当错误文本返回，日志里表现为
    "<bound method _InactiveRpcError.details of ...>"，必须调用后取值。
    """
    details = getattr(e, "details", None)
    if callable(details):
        try:
            details = details()
        except Exception:
            details = None
    return details or str(e)
