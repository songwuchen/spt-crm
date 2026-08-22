# -*- coding: utf-8 -*-
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.stdout.reconfigure(encoding="utf-8")

REG = {
    "财务审核": ["442558535226341870"],
    "生产": ["02374913228906"],
    "采购": ["02352513566524"],
    "仓库": ["01346931076927160185", "0654354430671114"],
    "质检": ["0236420233847"],
    "生产办（旋振筛）": ["02425350081942"],
    "采购（旋振筛）": ["286057106726080520"],
    "质检（旋振筛）": ["02362247571234189"],
    "仓库（旋振筛）": ["26140402631151393"],
}
REVIEW = {
    "区域经理/组长": ["(表单人员 region_manager_id)"],
    "业务部门审批": ["(发起人部门负责人)"],
    "信息情报部审批": ["023656363429294971"],
    "法务审批": ["543355140326074979", "4723152427763414", "256932256424153873"],
    "法务主管审批": ["02364840011125"],
    "设计审批": ["02364335378133"],
    "财务总监意见": ["0433406811775721"],  # 张光（无需李晋）
    "出口审批": ["01000533004677"],
    "生产审批": ["01210720669288"],
    "采购审批": ["02352513566524"],
    "质检审批": ["0236420233847"],
    "发起人": ["(发起人)"],
    "信息反馈": ["(发起人)"],
    "反馈区域经理/组长": ["(表单人员 region_manager_id)"],
    "反馈业务部门": ["(发起人部门负责人)"],
    "设计审批1": ["02364335378133"],
    "总经理审批": ["02336214315748"],
    "财务意见": ["0433406811775721"],
}


async def main():
    eng = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/spt_crm"
    )
    async with eng.connect() as c:
        rows = (
            await c.execute(text("select username, real_name from users"))
        ).fetchall()
    await eng.dispose()
    m = {u: n for u, n in rows}

    def fmt(usernames):
        parts = []
        for u in usernames:
            if u.startswith("("):
                parts.append(u)
            else:
                parts.append(f"{m.get(u) or '?'}（{u}）")
        return "、".join(parts)

    print("【合同登记审批】")
    for k, v in REG.items():
        print(f"  {k}: {fmt(v)}")
    print("【合同评审会签】")
    for k, v in REVIEW.items():
        print(f"  {k}: {fmt(v)}")


if __name__ == "__main__":
    asyncio.run(main())
