"""Seed script: populates demo business data for testing and demonstration.
Run AFTER seed.py (which creates permissions, roles, tenant, admin user).

Usage: python seed_demo_data.py
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import random

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.domains.auth.models import User, UserRole, Role
from app.domains.customer.models import Customer, Contact
from app.domains.lead.models import Lead
from app.domains.project.models import OpportunityProject
from app.domains.activity.models import Activity

TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _id():
    return str(uuid.uuid4())


def _days_ago(n: int):
    return datetime.now(timezone.utc) - timedelta(days=n)


async def main():
    async with async_session_factory() as db:
        # Check if demo data already exists
        existing = (await db.execute(
            select(Customer).where(Customer.tenant_id == TENANT_ID).limit(1)
        )).scalar_one_or_none()
        if existing:
            print("Demo data already exists, skipping.")
            return

        # Get admin user
        admin = (await db.execute(
            select(User).where(User.username == "admin")
        )).scalar_one_or_none()
        if not admin:
            print("Admin user not found. Run seed.py first.")
            return
        admin_id = admin.id
        admin_name = admin.real_name or "管理员"

        # Get sales_rep role for demo users
        sales_rep_role = (await db.execute(
            select(Role).where(Role.tenant_id == TENANT_ID, Role.code == "sales_rep")
        )).scalar_one_or_none()
        sales_mgr_role = (await db.execute(
            select(Role).where(Role.tenant_id == TENANT_ID, Role.code == "sales_manager")
        )).scalar_one_or_none()

        # ============================================================
        # 1. Demo Users (sales team)
        # ============================================================
        import bcrypt
        pw_hash = bcrypt.hashpw("demo123".encode(), bcrypt.gensalt()).decode()

        demo_users = []
        user_data = [
            ("zhangwei", "张伟", "13800001001", "zhangwei@demo.com"),
            ("lina", "李娜", "13800001002", "lina@demo.com"),
            ("wangfang", "王芳", "13800001003", "wangfang@demo.com"),
        ]
        for uname, rname, phone, email in user_data:
            uid = _id()
            u = User(id=uid, tenant_id=TENANT_ID, username=uname, password_hash=pw_hash,
                     real_name=rname, phone=phone, email=email)
            db.add(u)
            demo_users.append((uid, rname))
            # Assign roles
            if sales_rep_role:
                db.add(UserRole(id=_id(), tenant_id=TENANT_ID, user_id=uid, role_id=sales_rep_role.id))
            if rname == "张伟" and sales_mgr_role:
                db.add(UserRole(id=_id(), tenant_id=TENANT_ID, user_id=uid, role_id=sales_mgr_role.id))

        all_owners = [(admin_id, admin_name)] + demo_users

        # ============================================================
        # 2. Customers
        # ============================================================
        customers = []
        customer_data = [
            ("中芯科技有限公司", "中芯科技", "半导体", "大型", "华东", "A", "上海市浦东新区张江高科技园区", "expo"),
            ("华远汽车零部件集团", "华远汽车", "汽车零部件", "特大型", "华南", "A", "广州市番禺区大石工业园", "referral"),
            ("东方精密机械股份", "东方精密", "机械装备", "中型", "华东", "B", "苏州市工业园区星湖街", "inbound"),
            ("飞鹰航空制造公司", "飞鹰航空", "航空航天", "大型", "西南", "A", "成都市高新区天府大道", "partner"),
            ("瑞康医疗器械有限公司", "瑞康医疗", "医疗器械", "中型", "华北", "B", "北京市大兴区生物医药基地", "expo"),
            ("新能通新能源科技", "新能通", "新能源", "中型", "华东", "C", "杭州市余杭区未来科技城", "ad"),
            ("金固电子制造有限公司", "金固电子", "电子制造", "小型", "华南", "C", "深圳市宝安区福永街道", "call"),
            ("鸿达装备技术公司", "鸿达装备", "机械装备", "大型", "华中", "B", "武汉市东湖高新区光谷大道", "referral"),
        ]
        for name, short, industry, scale, region, level, addr, source in customer_data:
            owner = random.choice(all_owners)
            cid = _id()
            now = _days_ago(random.randint(10, 90))
            seq = random.randint(1000, 9999)
            c = Customer(
                id=cid, tenant_id=TENANT_ID,
                customer_code=f"CUS-{now.strftime('%Y%m%d')}-{seq}",
                name=name, short_name=short, industry=industry,
                scale_level=scale, region=region, level=level,
                address=addr, source=source,
                owner_id=owner[0], owner_name=owner[1],
                created_at=now, updated_at=now,
            )
            db.add(c)
            customers.append((cid, name, owner))

        # ============================================================
        # 3. Contacts (2 per customer)
        # ============================================================
        contact_titles = ["技术总监", "采购经理", "项目经理", "总工程师", "生产部长", "研发主管"]
        surnames = ["陈", "刘", "赵", "黄", "周", "吴", "孙", "杨"]
        given_names = ["明", "华", "强", "丽", "军", "磊", "洋", "静"]
        for cid, cname, _ in customers:
            for i in range(2):
                name = random.choice(surnames) + random.choice(given_names)
                db.add(Contact(
                    id=_id(), tenant_id=TENANT_ID, customer_id=cid,
                    name=name, title=random.choice(contact_titles),
                    phone=f"138{random.randint(10000000, 99999999)}",
                    email=f"{name}@example.com",
                    is_primary=(i == 0),
                ))

        # ============================================================
        # 4. Leads (mix of statuses)
        # ============================================================
        lead_data = [
            ("华远汽车ABS系统升级需求", "华远汽车零部件集团", "referral", "汽车零部件", "华南", "100-500万", "new"),
            ("中芯科技晶圆检测设备采购", "中芯科技有限公司", "expo", "半导体", "华东", "500万以上", "following"),
            ("东方精密CNC产线改造", "东方精密机械股份", "inbound", "机械装备", "华东", "50-100万", "following"),
            ("某医疗企业灭菌设备更新", "未知", "ad", "医疗器械", "华北", "10-50万", "new"),
            ("新能源电池包测试线", "新能通新能源科技", "partner", "新能源", "华东", "100-500万", "qualified"),
            ("金固电子SMT产线扩容", "金固电子制造有限公司", "call", "电子制造", "华南", "50-100万", "discarded"),
        ]
        for title, company, source, industry, region, budget, status in lead_data:
            owner = random.choice(all_owners)
            now = _days_ago(random.randint(5, 60))
            seq = random.randint(1000, 9999)
            lead = Lead(
                id=_id(), tenant_id=TENANT_ID,
                lead_code=f"LD-{now.strftime('%Y%m%d')}-{seq}",
                title=title, company_name=company,
                source=source, industry=industry, region=region,
                budget_range=budget, status=status, score=random.randint(30, 90),
                contact_name=random.choice(surnames) + random.choice(given_names),
                contact_phone=f"139{random.randint(10000000, 99999999)}",
                demand_summary=f"{title}，客户需求评估中",
                owner_id=owner[0], owner_name=owner[1],
                created_at=now, updated_at=now,
            )
            db.add(lead)

        # ============================================================
        # 5. Opportunity Projects (different stages)
        # ============================================================
        projects = []
        project_data = [
            ("中芯科技晶圆检测产线", 0, "S3", 5200000, 60, "active", "M", 30),
            ("飞鹰航空发动机测试台", 1, "S4", 8800000, 75, "active", "H", 20),
            ("瑞康医疗灭菌设备采购", 2, "S2", 1500000, 40, "active", "L", 60),
            ("华远汽车总装线升级", 3, "S5", 12000000, 85, "active", "M", 15),
            ("鸿达装备数控中心改造", 4, "S1", 3500000, 30, "active", "L", 90),
            ("东方精密自动化产线", 5, "S6", 6500000, 95, "won", "L", 5),
        ]
        for name, cust_idx, stage, amount, prob, status, risk, days in project_data:
            cid, cname, _ = customers[cust_idx]
            owner = random.choice(all_owners)
            now = _days_ago(days + random.randint(0, 30))
            seq = random.randint(1000, 9999)
            pid = _id()
            p = OpportunityProject(
                id=pid, tenant_id=TENANT_ID,
                project_no=f"OPP-{now.strftime('%Y%m%d')}-{seq}",
                name=name, customer_id=cid, customer_name=cname,
                stage_code=stage, status=status,
                amount_expect=amount, probability=prob,
                risk_level=risk,
                close_date_expect=(datetime.now() + timedelta(days=random.randint(30, 180))).strftime("%Y-%m-%d"),
                owner_id=owner[0], owner_name=owner[1],
                created_by_id=owner[0], created_by_name=owner[1],
                created_at=now, updated_at=now,
            )
            db.add(p)
            projects.append((pid, name, owner))

            # Add activity for project creation
            db.add(Activity(
                id=_id(), tenant_id=TENANT_ID,
                biz_type="project", biz_id=pid,
                activity_type="system",
                subject=f"创建商机项目: {name}",
                created_by_id=owner[0], created_by_name=owner[1],
                created_at=now,
            ))

        await db.commit()
        print(f"Demo data seeded successfully:")
        print(f"  - {len(demo_users)} demo users (password: demo123)")
        print(f"  - {len(customers)} customers with contacts")
        print(f"  - {len(lead_data)} leads")
        print(f"  - {len(projects)} opportunity projects")


if __name__ == "__main__":
    asyncio.run(main())
