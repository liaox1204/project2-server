"""种子数据：服务目录 demo 数据 + 管理员账号。运行一次即可。"""
import asyncio

from config.Stu import async_engine, AsyncSessionLocal
from core.security import hash_password
from models.models import Base, Service, User


SERVICES = [
    {"service_code": "escort_001", "service_type": "escort_medical", "title": "陪诊服务",
     "description": "专人陪同老人就医，协助挂号、缴费、取药", "price": 80, "price_unit": "次",
     "city": "", "need_family_confirm": 0},
    {"service_code": "cleaning_001", "service_type": "cleaning", "title": "家政保洁",
     "description": "上门打扫卫生、整理家务", "price": 60, "price_unit": "小时",
     "city": "", "need_family_confirm": 0},
    {"service_code": "buy_med_001", "service_type": "buy_medicine", "title": "代买药",
     "description": "按老人提供的药品清单代购并送药上门", "price": 20, "price_unit": "次",
     "city": "", "need_family_confirm": 0},
    {"service_code": "pickup_001", "service_type": "pickup", "title": "代取快递",
     "description": "帮忙到驿站代取快递送上门", "price": 10, "price_unit": "次",
     "city": "", "need_family_confirm": 0},
    {"service_code": "repair_001", "service_type": "repair", "title": "上门维修",
     "description": "水电、家电、管道等上门维修", "price": 120, "price_unit": "次",
     "city": "", "need_family_confirm": 1},
]


async def seed():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        # 服务目录
        for svc in SERVICES:
            res = await session.execute(select(Service).where(Service.service_code == svc["service_code"]))
            if res.scalar_one_or_none() is None:
                session.add(Service(**svc))

        # 管理员账号（后台管理登录用）
        res = await session.execute(select(User).where(User.phone == "13800000000"))
        if res.scalar_one_or_none() is None:
            session.add(User(
                role_type="admin", name="管理员", phone="13800000000",
                password_hash=hash_password("admin123"),
            ))

        await session.commit()
    print("种子数据已写入（服务目录 + 管理员账号 admin/13800000000/admin123）")


if __name__ == "__main__":
    asyncio.run(seed())
