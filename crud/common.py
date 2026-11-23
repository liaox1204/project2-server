"""通用工具：订单号/事件号生成。"""
import time
import random

_pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def gen_order_no(prefix: str = "O") -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    rnd = "".join(random.choices(_pool, k=6))
    return f"{prefix}{ts}{rnd}"


def gen_event_no(prefix: str = "E") -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    rnd = "".join(random.choices(_pool, k=6))
    return f"{prefix}{ts}{rnd}"


def gen_invite_code() -> str:
    return "".join(random.choices(_pool, k=10))


def gen_session_id() -> str:
    ts = time.strftime("%Y%m%d%H%M%S")
    rnd = "".join(random.choices(_pool, k=4))
    return f"s_{ts}_{rnd}"
