import asyncio
from models import database

async def run():
    try:
        await database.ensure_pnl_columns(database.engine)
        print('ensure_pnl_columns completed')
    except Exception as e:
        print('ensure_pnl_columns raised:', repr(e))

if __name__ == '__main__':
    asyncio.run(run())
