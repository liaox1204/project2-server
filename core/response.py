"""统一响应体与错误码。"""
from typing import Any
from fastapi.responses import JSONResponse
from fastapi import Request


class BizError(Exception):
    """业务异常，携带错误码。"""

    def __init__(self, code: int, message: str = "", status_code: int = 200):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.status_code = status_code
        super().__init__(self.message)


# 错误码分区
ERROR_MESSAGES = {
    # 10xxx 通用
    10001: "参数错误",
    10002: "未登录或登录已过期",
    10003: "权限不足",
    10004: "请求过于频繁，请稍后再试",
    10005: "资源不存在",
    # 20xxx 用户与亲情绑定
    20001: "手机号格式错误",
    20002: "验证码错误或已过期",
    20003: "该手机号已被绑定",
    20004: "已存在绑定关系",
    20005: "绑定关系不存在",
    # 30xxx 健康数据
    30001: "健康数据类型不支持",
    30002: "健康数据格式错误",
    # 40xxx 服务与订单
    40001: "服务不存在",
    40002: "订单不存在",
    40003: "订单状态不允许该操作",
    # 50xxx 支付
    50001: "支付失败",
    # 60xxx 提醒与通知
    60001: "提醒不存在",
    # 70xxx AI能力
    70001: "语音识别失败",
    70002: "AI服务暂时不可用",
    70003: "AI工具调用失败",
    70004: "该操作需要确认",
    # 80xxx 风控与求助
    80001: "求助事件不存在",
}

CODE_SUCCESS = 0
CODE_SYSTEM_ERROR = 99999


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": CODE_SUCCESS, "message": message, "data": data}


def fail(code: int, message: str = "") -> dict:
    return {"code": code, "message": message or ERROR_MESSAGES.get(code, "未知错误"), "data": None}


# 全局异常处理器
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )
