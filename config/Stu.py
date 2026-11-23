from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # 引入异步引擎

# 连接数据库（trigger 是 MySQL 保留字，URL 中直接使用即可由 aiomysql 处理）
ASYNC_DATABASE_URL = "mysql+aiomysql://root:root@localhost:3306/trigger?charset=utf8mb4"

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,          # 可选:输出SQL日志
    pool_size=10,        # 设置连接池中保持的持久连接数
    max_overflow=20,     # 设置连接池允许创建的额外连接数
    pool_pre_ping=True,  # 连接前探活，避免断连
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,       # 绑定数据库引擎
    class_=AsyncSession,     # 指定会话类
    expire_on_commit=False,  # 提交后会话不过期
)


# 依赖项
async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
