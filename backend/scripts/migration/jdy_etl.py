#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简道云 (JianDaoYun) -> SPT-CRM ETL.

Runs INSIDE the prod backend container (has asyncpg + httpx + DATABASE_URL,
and can reach the 简道云 gateway at 192.168.0.6:8011).

Design:
  * Idempotent: every created row is recorded in `_migration_map`
    (source_form, source_id, target_table -> target_id). Re-runs skip mapped rows.
  * Contract join keys recorded in `_contract_join` so payments/invoices can
    attach to the synthesized project.
  * Master data (customers/users/departments) is ALREADY in prod; we link by name.
    Customers are auto-created on miss, tagged custom_fields_json._src='jdy_migration'.

Usage (inside container):
  python jdy_etl.py <phase> [limit]
  phase: projects | contracts | payments | invoices | service | activities | counts
  limit: optional int for pilot runs (0 / omitted = all)
"""
import asyncio, os, sys, uuid, json, re
from datetime import datetime, timezone
import httpx
import asyncpg

KEY = os.environ.get("JDY_KEY", "")  # set JDY_KEY env var (简道云 gateway X-API-Key)
BASE = "http://192.168.0.6:8011/api"
TENANT = "00000000-0000-0000-0000-000000000001"
DBURL = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")

APP_SALES = "5de0b3e85600ec0006f420f2"
APP_DC = "56ca77ce1efc301d279b8a4d"
APP_SVC = "58e2fbc7ffd1608b4ce92809"

FORM = {
    "projects":   (APP_SALES, "636ca7a4493618000af57265"),   # 申报信息
    "contracts":  (APP_DC,    "5d118dc922ba776f27472706"),   # 合同登记表
    "payments":   (APP_DC,    "5d63721786b06824f3fcc07f"),   # 收款登记流程
    "invoices":   (APP_DC,    "5dd34ddf26aecf000655a354"),   # 开票申请
    "service":    (APP_SVC,   "5e06c8a92675f1000634baf1"),   # 客户服务申请及反馈
    "activities": (APP_SALES, "5de0b5350488db0006a109da"),   # 销售日志
}

def now():
    return datetime.now(timezone.utc)

def parse_dt(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None

def name_of(v):
    """Extract a person/dept display name from a user/dept widget value."""
    if v is None:
        return None
    if isinstance(v, list):
        for x in v:
            n = name_of(x)
            if n:
                return n
        return None
    if isinstance(v, dict):
        return (v.get("name") or v.get("text") or "").strip() or None
    s = str(v).strip()
    return s or None

def text_of(v):
    if v is None:
        return None
    if isinstance(v, dict):
        if any(k in v for k in ("province", "city", "district", "detail")):
            return " ".join(str(v.get(k, "")) for k in ("province", "city", "district", "detail") if v.get(k)) or None
        return (v.get("name") or v.get("text") or "").strip() or None
    if isinstance(v, list):
        parts = [text_of(x) for x in v]
        parts = [p for p in parts if p]
        return ", ".join(parts) or None
    s = str(v).strip()
    return s or None

def num_of(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None

def norm(s):
    if not s:
        return ""
    return re.sub(r"\s+", "", str(s)).replace("（", "(").replace("）", ")").strip()

# ----------------- HTTP -----------------
async def fetch_fields(c, app, form):
    r = await c.get(f"{BASE}/form/{app}/{form}/fields")
    fields = r.json()["data"]["fields"]
    lbl = {}
    for f in fields:
        lbl.setdefault(f["text"], f["name"])
    return lbl

async def _stat_total(c, app, form):
    try:
        r = await c.post(f"{BASE}/form/statistics", json={"app_id": app, "entry_id": form, "filter": {"cond": [], "rel": "and"}})
        return int(r.json()["data"]["totalCount"])
    except Exception:
        return 0

async def iter_rows(c, app, form, batch=200, limit=0):
    """Robust pagination: walk every window up to the statistics total so a
    transient short/empty page can't end the loop early. Retries per window."""
    total = await _stat_total(c, app, form)
    skip = 0
    got = 0
    # hard ceiling so we never loop forever; +2 windows of slack past total
    ceiling = (total + batch * 2) if total else 10 ** 9
    empty_streak = 0
    while skip < ceiling:
        rows = None
        for attempt in range(3):
            try:
                r = await c.post(f"{BASE}/form/list", json={
                    "app_id": app, "entry_id": form,
                    "filter": {"cond": [], "rel": "and"}, "skip": skip, "limit": batch})
                rows = r.json().get("data", {}).get("data", [])
                break
            except Exception:
                if attempt == 2:
                    rows = []
                await asyncio.sleep(1)
        if not rows:
            empty_streak += 1
            # if we already passed the known total, a real end; else tolerate a couple blanks
            if (total and skip >= total) or empty_streak >= 3:
                break
            skip += batch
            continue
        empty_streak = 0
        for row in rows:
            yield row
            got += 1
            if limit and got >= limit:
                return
        skip += batch

def pick(lbl, row, *labels):
    for L in labels:
        nm = lbl.get(L)
        if nm and row.get(nm) not in (None, "", [], {}):
            return row.get(nm)
    return None

# ----------------- DB helpers -----------------
async def ensure_aux(conn):
    await conn.execute("""
        create table if not exists _migration_map(
          source_form text, source_id text, target_table text, target_id text,
          created_at timestamptz default now(),
          primary key (source_form, source_id, target_table));
        create table if not exists _contract_join(
          join_key text primary key, project_id text, contract_id text);
    """)

async def load_masters(conn):
    cust = {}
    for r in await conn.fetch("select id,name from customers where tenant_id=$1 and coalesce(is_deleted,false)=false", TENANT):
        if r["name"]:
            cust.setdefault(norm(r["name"]), r["id"])
    users = {}
    for r in await conn.fetch("select id,real_name from users where tenant_id=$1", TENANT):
        if r["real_name"]:
            users.setdefault(norm(r["real_name"]), r["id"])
    depts = {}
    for r in await conn.fetch("select id,name from departments where tenant_id=$1", TENANT):
        if r["name"]:
            depts.setdefault(norm(r["name"]), r["id"])
    return cust, users, depts

async def mapped_ids(conn, form, table):
    rows = await conn.fetch("select source_id from _migration_map where source_form=$1 and target_table=$2", form, table)
    return {r["source_id"] for r in rows}

def newid():
    return str(uuid.uuid4())

# ----------------- customer resolution -----------------
async def resolve_customer(conn, cust, company, owner_name, owner_id, created):
    """Return customer_id, creating a tagged customer on miss. company required."""
    if not company:
        return None
    key = norm(company)
    if key in cust:
        return cust[key]
    cid = newid()
    await conn.execute(
        """insert into customers(id,tenant_id,name,owner_id,owner_name,source,status,is_deleted,
                custom_fields_json,created_at,updated_at)
           values($1,$2,$3,$4,$5,'简道云迁移','active',false,$6,$7,$7)""",
        cid, TENANT, company[:300], owner_id, owner_name,
        json.dumps({"_src": "jdy_migration"}), created or now())
    cust[key] = cid
    return cid

# =================================================================
# PHASE: projects  (申报信息 -> opportunity_projects)
# =================================================================
def map_status(proj, final, bid):
    s = (proj or "").strip()
    if s == "已签合同":
        return ("won", "S6")
    if s == "中标":
        return ("won", "S5")
    if s in ("取消", "落标", "流标"):
        return ("lost", "S1")
    if s == "暂停":
        return ("suspended", "S2")
    if s == "进行中":
        return ("active", "S2")
    b = (bid or "").strip()
    if b == "中标":
        return ("won", "S5")
    if b in ("落标", "流标", "项目取消"):
        return ("lost", "S1")
    return ("active", "S1")

async def phase_projects(conn, c, limit):
    app, form = FORM["projects"]
    lbl = await fetch_fields(c, app, form)
    done = await mapped_ids(conn, form, "opportunity_projects")
    cust, users, depts = await load_masters(conn)
    seen_codes = {r["project_code"] for r in await conn.fetch(
        "select project_code from opportunity_projects where tenant_id=$1", TENANT)}
    ins_proj, ins_map = [], []
    n_total = n_new = n_cust_link = 0
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        if not sid or sid in done:
            continue
        company = text_of(pick(lbl, row, "公司名称"))
        owner_nm = name_of(pick(lbl, row, "*申报人", "申报人", "填表人")) or text_of(pick(lbl, row, "申报人（导入时用）"))
        owner_id = users.get(norm(owner_nm)) if owner_nm else None
        created = parse_dt(row.get("createTime")) or now()
        updated = parse_dt(row.get("updateTime")) or created
        cid = cust.get(norm(company)) if company else None
        if cid:
            n_cust_link += 1
        code = text_of(pick(lbl, row, "项目编号", "项目编号（导入时过渡用）")) or ""
        if not code or code in seen_codes:
            code = "JDY-" + sid[-12:]
            if code in seen_codes:
                code = "JDY-" + sid
        seen_codes.add(code)
        nm = text_of(pick(lbl, row, "项目名称")) or company or "未命名项目"
        status, stage = map_status(
            text_of(pick(lbl, row, "项目状态")),
            text_of(pick(lbl, row, "项目最终状态")),
            text_of(pick(lbl, row, "中标情况")))
        cf = {
            "_src": "jdy", "_src_id": sid,
            "来源": text_of(pick(lbl, row, "来源")),
            "客户类型": text_of(pick(lbl, row, "客户类型")),
            "行业": text_of(pick(lbl, row, "行业")),
            "中标情况": text_of(pick(lbl, row, "中标情况")),
            "原因": text_of(pick(lbl, row, "原因")),
            "国别": text_of(pick(lbl, row, "国别")),
            "项目地址": text_of(pick(lbl, row, "项目地址")),
            "项目动态": text_of(pick(lbl, row, "项目动态")),
        }
        if not cid and company:
            cf["公司名称"] = company
        cf = {k: v for k, v in cf.items() if v not in (None, "")}
        pid = newid()
        ins_proj.append((pid, TENANT, code, cid, nm[:300], stage, status, owner_id,
                         owner_nm[:100] if owner_nm else None, json.dumps(cf, ensure_ascii=False),
                         created, updated))
        ins_map.append((form, sid, "opportunity_projects", pid))
        n_new += 1
        if len(ins_proj) >= 500:
            await _flush_projects(conn, ins_proj, ins_map)
            ins_proj, ins_map = [], []
            print(f"  ... {n_new} new ({n_cust_link} linked to customer)", flush=True)
    if ins_proj:
        await _flush_projects(conn, ins_proj, ins_map)
    print(f"[projects] source={n_total} new={n_new} customer-linked={n_cust_link} skipped(existing)={n_total-n_new}", flush=True)

async def _flush_projects(conn, ins_proj, ins_map):
    async with conn.transaction():
        await conn.executemany(
            """insert into opportunity_projects
               (id,tenant_id,project_code,customer_id,name,stage_code,status,owner_id,owner_name,
                custom_fields_json,created_at,updated_at,is_deleted)
               values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,false)""", ins_proj)
        await conn.executemany(
            "insert into _migration_map(source_form,source_id,target_table,target_id) values($1,$2,$3,$4) on conflict do nothing",
            ins_map)

# =================================================================
# PHASE: service  (客户服务申请及反馈 -> service_tickets)
# =================================================================
def map_svc_type(v):
    s = v or ""
    if "售后" in s:
        return "fault"
    if "售中" in s:
        return "maintenance"
    if "售前" in s:
        return "training"
    return "fault"

def map_priority(v):
    s = v or ""
    if "非常紧急" in s:
        return "critical"
    if "紧急" in s:
        return "high"
    return "medium"

async def phase_service(conn, c, limit):
    app, form = FORM["service"]
    lbl = await fetch_fields(c, app, form)
    done = await mapped_ids(conn, form, "service_tickets")
    cust, users, depts = await load_masters(conn)
    ins, ins_map = [], []
    n_total = n_new = 0
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        if not sid or sid in done:
            continue
        company = text_of(pick(lbl, row, "客户名称"))
        cid = cust.get(norm(company)) if company else None
        owner_nm = name_of(pick(lbl, row, "业务员"))
        created = parse_dt(row.get("createTime")) or now()
        updated = parse_dt(row.get("updateTime")) or created
        tno = text_of(pick(lbl, row, "流水号")) or ("KF-" + sid[-12:])
        ttype = map_svc_type(text_of(pick(lbl, row, "服务性质")))
        prio = map_priority(text_of(pick(lbl, row, "紧急情况")))
        desc_parts = [text_of(pick(lbl, row, "服务要求")), text_of(pick(lbl, row, "服务地点")),
                      text_of(pick(lbl, row, "备注"))]
        desc = " | ".join(p for p in desc_parts if p) or None
        tid = newid()
        ins.append((tid, TENANT, cid, tno, ttype, prio, "closed", desc,
                    owner_nm[:100] if owner_nm else None, created, updated))
        ins_map.append((form, sid, "service_tickets", tid))
        n_new += 1
        if len(ins) >= 500:
            await _flush_service(conn, ins, ins_map)
            ins, ins_map = [], []
    if ins:
        await _flush_service(conn, ins, ins_map)
    print(f"[service] source={n_total} new={n_new} skipped(existing)={n_total-n_new}", flush=True)

async def _flush_service(conn, ins, ins_map):
    async with conn.transaction():
        await conn.executemany(
            """insert into service_tickets
               (id,tenant_id,customer_id,ticket_no,type,priority,status,description,created_by_name,created_at,updated_at)
               values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""", ins)
        await conn.executemany(
            "insert into _migration_map(source_form,source_id,target_table,target_id) values($1,$2,$3,$4) on conflict do nothing",
            ins_map)

# =================================================================
# PHASE: contracts  (合同登记表 -> project + contract + version + join keys)
# =================================================================
async def phase_contracts(conn, c, limit):
    app, form = FORM["contracts"]
    lbl = await fetch_fields(c, app, form)
    done = await mapped_ids(conn, form, "contracts")
    cust, users, depts = await load_masters(conn)
    seen_pcode = {r["project_code"] for r in await conn.fetch("select project_code from opportunity_projects where tenant_id=$1", TENANT)}
    seen_cno = {r["contract_no"] for r in await conn.fetch("select contract_no from contracts where tenant_id=$1", TENANT)}
    n_total = n_new = n_cust_new = 0
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        if not sid or sid in done:
            continue
        company = text_of(pick(lbl, row, "单位名称"))
        owner_nm = name_of(pick(lbl, row, "业务人员"))
        owner_id = users.get(norm(owner_nm)) if owner_nm else None
        created = parse_dt(row.get("createTime")) or now()
        updated = parse_dt(row.get("updateTime")) or created
        hetong = text_of(pick(lbl, row, "合同号"))
        tuzhi = text_of(pick(lbl, row, "图纸编号"))
        amount = num_of(pick(lbl, row, "合同总金额"))
        before = len(cust)
        cid = await resolve_customer(conn, cust, company, owner_nm, owner_id, created) if company else None
        if len(cust) > before:
            n_cust_new += 1
        # project
        pcode = "HT-" + (hetong or text_of(pick(lbl, row, "流水号")) or sid[-10:])
        if pcode in seen_pcode:
            pcode = "HT-" + sid[-12:]
        seen_pcode.add(pcode)
        pname = text_of(pick(lbl, row, "项目名称")) or (("合同 " + hetong) if hetong else None) or company or "合同项目"
        cf = {"_src": "jdy_contract", "_src_id": sid, "合同号": hetong, "图纸编号": tuzhi}
        cf = {k: v for k, v in cf.items() if v}
        pid = newid()
        await conn.execute(
            """insert into opportunity_projects
               (id,tenant_id,project_code,customer_id,name,stage_code,status,amount_expect,owner_id,owner_name,
                custom_fields_json,created_at,updated_at,is_deleted)
               values($1,$2,$3,$4,$5,'S6','won',$6,$7,$8,$9,$10,$11,false)""",
            pid, TENANT, pcode, cid, pname[:300], amount, owner_id,
            owner_nm[:100] if owner_nm else None, json.dumps(cf, ensure_ascii=False), created, updated)
        # contract
        cno = hetong or text_of(pick(lbl, row, "流水号")) or ("HT-" + sid[-10:])
        if cno in seen_cno:
            cno = cno + "-" + sid[-6:]
        seen_cno.add(cno)
        signed = parse_dt(pick(lbl, row, "订货日期")) or parse_dt(pick(lbl, row, "下卡日期"))
        pay_plan = pick(lbl, row, "收款计划")
        ctid = newid()
        await conn.execute(
            """insert into contracts
               (id,tenant_id,project_id,contract_no,current_version_no,status,signed_date,amount_total,
                payment_terms_json,created_by_name,created_at,updated_at)
               values($1,$2,$3,$4,1,'signed',$5,$6,$7,$8,$9,$10)""",
            ctid, TENANT, pid, cno[:64], (signed.date() if signed else None), amount,
            json.dumps(pay_plan, ensure_ascii=False) if pay_plan else None,
            owner_nm[:100] if owner_nm else None, created, updated)
        details = pick(lbl, row, "合同明细")
        await conn.execute(
            """insert into contract_versions
               (id,tenant_id,contract_id,version_no,title,key_clauses_json,status,created_at,updated_at)
               values($1,$2,$3,1,$4,$5,'signed',$6,$7)""",
            newid(), TENANT, ctid, cno[:200],
            json.dumps(details, ensure_ascii=False) if details else None, created, updated)
        # join keys
        for jk in (hetong, tuzhi):
            if jk:
                await conn.execute("insert into _contract_join(join_key,project_id,contract_id) values($1,$2,$3) on conflict do nothing", jk, pid, ctid)
        await conn.execute("insert into _migration_map values($1,$2,'opportunity_projects',$3) on conflict do nothing", form, sid, pid)
        await conn.execute("insert into _migration_map values($1,$2,'contracts',$3) on conflict do nothing", form, sid, ctid)
        n_new += 1
        if n_new % 500 == 0:
            print(f"  ... {n_new} contracts ({n_cust_new} new customers created)", flush=True)
    print(f"[contracts] source={n_total} new={n_new} new_customers={n_cust_new} skipped(existing)={n_total-n_new}", flush=True)

# sub-widget ids inside 收款.款项分配
PAY_TUZHI = "_widget_1566798361303"   # 图纸编号
PAY_HETONG = "_widget_1708572036504"  # 合同号
PAY_KIND = "_widget_1583377647110"    # 款项性质
PAY_AMT = "_widget_1566798361344"     # 分配金额

async def phase_payments(conn, c, limit):
    app, form = FORM["payments"]
    lbl = await fetch_fields(c, app, form)
    join = {r["join_key"]: r["project_id"] for r in await conn.fetch("select join_key,project_id from _contract_join")}
    done = await mapped_ids(conn, form, "payment_records")
    n_total = n_new = n_noproj = 0
    ins, ins_map = [], []
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        recv = parse_dt(pick(lbl, row, "来款日期"))
        recv_no = text_of(pick(lbl, row, "收款号"))
        allocs = pick(lbl, row, "款项分配") or []
        for idx, a in enumerate(allocs if isinstance(allocs, list) else []):
            msid = f"{sid}#{idx}"
            if msid in done:
                continue
            jk = a.get(PAY_HETONG) or a.get(PAY_TUZHI)
            pid = join.get(jk) if jk else None
            amt = num_of(a.get(PAY_AMT))
            if not pid or not amt:
                n_noproj += 1
                continue
            rid = newid()
            ins.append((rid, TENANT, pid, (recv.date() if recv else None), amt,
                        text_of(a.get(PAY_KIND)) or "简道云", recv_no, recv or now(), recv or now()))
            ins_map.append((form, msid, "payment_records", rid))
            n_new += 1
            if len(ins) >= 500:
                await _flush_payments(conn, ins, ins_map); ins, ins_map = [], []
                print(f"  ... {n_new} payments", flush=True)
    if ins:
        await _flush_payments(conn, ins, ins_map)
    print(f"[payments] source_rows={n_total} new_records={n_new} no_project_match={n_noproj}", flush=True)

async def _flush_payments(conn, ins, ins_map):
    async with conn.transaction():
        await conn.executemany(
            """insert into payment_records(id,tenant_id,project_id,received_date,amount,channel,reference_no,created_at,updated_at)
               values($1,$2,$3,$4,$5,$6,$7,$8,$9)""", ins)
        await conn.executemany("insert into _migration_map(source_form,source_id,target_table,target_id) values($1,$2,$3,$4) on conflict do nothing", ins_map)

async def phase_invoices(conn, c, limit):
    app, form = FORM["invoices"]
    lbl = await fetch_fields(c, app, form)
    join = {r["join_key"]: r["project_id"] for r in await conn.fetch("select join_key,project_id from _contract_join")}
    done = await mapped_ids(conn, form, "invoices")
    seen = set()
    n_total = n_new = n_noproj = 0
    ins, ins_map = [], []
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        if not sid or sid in done:
            continue
        jk = text_of(pick(lbl, row, "图纸编号"))
        pid = join.get(jk) if jk else None
        if not pid:
            n_noproj += 1
            continue
        ino = text_of(pick(lbl, row, "发票号码")) or text_of(pick(lbl, row, "流水号")) or ("FP-" + sid[-10:])
        if ino in seen:
            ino = ino + "-" + sid[-6:]
        seen.add(ino)
        amt = num_of(pick(lbl, row, "总价合计"))
        idate = parse_dt(pick(lbl, row, "开票时间")) or parse_dt(pick(lbl, row, "申请日期"))
        created = parse_dt(row.get("createTime")) or now()
        rid = newid()
        ins.append((rid, TENANT, pid, ino[:100], amt, (idate.date() if idate else None), "issued", created, created))
        ins_map.append((form, sid, "invoices", rid))
        n_new += 1
        if len(ins) >= 500:
            await _flush_invoices(conn, ins, ins_map); ins, ins_map = [], []
            print(f"  ... {n_new} invoices", flush=True)
    if ins:
        await _flush_invoices(conn, ins, ins_map)
    print(f"[invoices] source={n_total} new={n_new} no_project_match={n_noproj} skipped(existing)={n_total-n_new-n_noproj}", flush=True)

async def _flush_invoices(conn, ins, ins_map):
    async with conn.transaction():
        await conn.executemany(
            """insert into invoices(id,tenant_id,project_id,invoice_no,amount,invoice_date,status,created_at,updated_at)
               values($1,$2,$3,$4,$5,$6,$7,$8,$9)""", ins)
        await conn.executemany("insert into _migration_map(source_form,source_id,target_table,target_id) values($1,$2,$3,$4) on conflict do nothing", ins_map)

# =================================================================
# PHASE: activities  (销售日志 -> activities, biz=customer)
# =================================================================
def map_act_type(v):
    s = v or ""
    if "电话" in s:
        return "call"
    if "网络" in s:
        return "meeting"
    if "当面" in s or "拜访" in s:
        return "visit"
    return "note"

async def phase_activities(conn, c, limit):
    app, form = FORM["activities"]
    lbl = await fetch_fields(c, app, form)
    cust, users, depts = await load_masters(conn)
    done = await mapped_ids(conn, form, "activities")
    n_total = n_new = n_nocust = 0
    ins, ins_map = [], []
    async for row in iter_rows(c, app, form, limit=limit):
        n_total += 1
        sid = row.get("_id")
        if not sid or sid in done:
            continue
        company = text_of(pick(lbl, row, "客户名称"))
        cid = cust.get(norm(company)) if company else None
        if not cid:
            n_nocust += 1
            continue
        author = name_of(pick(lbl, row, "填写人"))
        author_id = users.get(norm(author)) if author else None
        created = parse_dt(pick(lbl, row, "日志日期")) or parse_dt(row.get("createTime")) or now()
        updated = parse_dt(row.get("updateTime")) or created
        content = " | ".join(p for p in [text_of(pick(lbl, row, "跟进情况详细描述")),
                                          text_of(pick(lbl, row, "今日完成工作"))] if p) or None
        subject = text_of(pick(lbl, row, "跟进信息")) or "销售跟进"
        nfd = parse_dt(pick(lbl, row, "下次跟进时间"))
        rid = newid()
        ins.append((rid, TENANT, "customer", cid, map_act_type(text_of(pick(lbl, row, "跟进方式"))),
                    subject[:300], content, (nfd.date() if nfd else None), company[:200] if company else None,
                    author_id, author[:100] if author else None, created, updated))
        ins_map.append((form, sid, "activities", rid))
        n_new += 1
        if len(ins) >= 500:
            await _flush_acts(conn, ins, ins_map); ins, ins_map = [], []
            print(f"  ... {n_new} activities", flush=True)
    if ins:
        await _flush_acts(conn, ins, ins_map)
    print(f"[activities] source={n_total} new={n_new} no_customer_match(skipped)={n_nocust}", flush=True)

async def _flush_acts(conn, ins, ins_map):
    async with conn.transaction():
        await conn.executemany(
            """insert into activities(id,tenant_id,biz_type,biz_id,activity_type,subject,content,next_follow_date,
                  biz_name,created_by_id,created_by_name,created_at,updated_at)
               values($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""", ins)
        await conn.executemany("insert into _migration_map(source_form,source_id,target_table,target_id) values($1,$2,$3,$4) on conflict do nothing", ins_map)

# =================================================================
# PHASE: relink  (attach orphan migrated projects to existing customers by name)
# =================================================================
async def _orphan_projects(conn):
    """Migrated projects with a 公司名称 but no linked customer."""
    return await conn.fetch(
        """select id, custom_fields_json->>'公司名称' as company
           from opportunity_projects
           where tenant_id=$1 and customer_id is null
             and custom_fields_json is not null
             and (custom_fields_json->>'公司名称') is not null
             and (custom_fields_json->>'公司名称') <> ''""", TENANT)


async def phase_relink_preview(conn, c, limit):
    cust, _, _ = await load_masters(conn)
    rows = await _orphan_projects(conn)
    matched = unmatched = 0
    samples_m, samples_u = [], []
    for r in rows:
        company = r["company"]
        if norm(company) in cust:
            matched += 1
            if len(samples_m) < 5:
                samples_m.append(company)
        else:
            unmatched += 1
            if len(samples_u) < 5:
                samples_u.append(company)
    total = len(rows)
    print(f"[relink-preview] orphan_projects={total} would_match={matched} "
          f"({(matched/total*100 if total else 0):.1f}%) would_NOT_match={unmatched}", flush=True)
    print("  sample matched:   " + " | ".join(samples_m), flush=True)
    print("  sample unmatched: " + " | ".join(samples_u), flush=True)


async def phase_relink_apply(conn, c, limit):
    """Link orphan projects to existing customers (by normalized name). Existing-only;
    does NOT create new customers. Idempotent (only touches customer_id IS NULL)."""
    cust, _, _ = await load_masters(conn)
    rows = await _orphan_projects(conn)
    updates = []
    for r in rows:
        cid = cust.get(norm(r["company"]))
        if cid:
            updates.append((cid, r["id"]))
    n = 0
    for i in range(0, len(updates), 500):
        chunk = updates[i:i + 500]
        async with conn.transaction():
            await conn.executemany(
                "update opportunity_projects set customer_id=$1 where id=$2 and customer_id is null", chunk)
        n += len(chunk)
        print(f"  ... relinked {n}", flush=True)
    print(f"[relink-apply] orphan_projects={len(rows)} relinked={len(updates)} "
          f"still_unmatched={len(rows)-len(updates)}", flush=True)


# =================================================================
async def phase_counts(conn, c, limit):
    for k, (app, form) in FORM.items():
        try:
            r = await c.post(f"{BASE}/form/statistics", json={"app_id": app, "entry_id": form, "filter": {"cond": [], "rel": "and"}})
            src = r.json()["data"]["totalCount"]
        except Exception as e:
            src = f"err:{e}"
        print(f"{k:12s} source={src}")
    print("---- prod target counts ----")
    for t in ("opportunity_projects", "contracts", "payment_records", "invoices", "service_tickets", "activities", "customers"):
        n = await conn.fetchval(f"select count(*) from {t} where tenant_id=$1", TENANT)
        m = await conn.fetchval("select count(*) from _migration_map where target_table=$1", t)
        print(f"  {t:22s} total={n} migrated={m}")

PHASES = {
    "projects": phase_projects,
    "contracts": phase_contracts,
    "payments": phase_payments,
    "invoices": phase_invoices,
    "service": phase_service,
    "activities": phase_activities,
    "relink-preview": phase_relink_preview,
    "relink-apply": phase_relink_apply,
    "counts": phase_counts,
}

async def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "counts"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    conn = await asyncpg.connect(DBURL)
    await ensure_aux(conn)
    async with httpx.AsyncClient(timeout=60, headers={"X-API-Key": KEY}) as c:
        fn = PHASES.get(phase)
        if not fn:
            print("unknown phase:", phase, "available:", list(PHASES))
            return
        print(f"=== PHASE {phase} (limit={limit or 'ALL'}) ===", flush=True)
        await fn(conn, c, limit)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
