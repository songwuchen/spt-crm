# 数据库升级到 pgvector（向量语义检索）— 运维说明

> 适用对象：**已部署 SPT-CRM、数据库还在 `postgres:16-alpine` 镜像**、希望启用「AI 知识库语义检索 / RAG 问答」的服务器。
> 本次代码已把知识库检索从「关键词匹配」升级为「pgvector 向量余弦检索」。要启用它，数据库镜像必须换成带 `pgvector` 扩展的 `pgvector/pgvector:pg16`。
> 未升级也不影响系统运行——知识库会**自动回退关键词检索**，其余功能（含对话模型 AI 分析）全部照常。

---

## 一、先搞清楚你的服务器属于哪种情况

| 情况 | 判断方法 | 怎么做 |
|---|---|---|
| **A. 全新部署**（数据库是空库，首次 `alembic upgrade`） | 该服务器还没跑过本项目 | 直接把 db 镜像设成 `pgvector/pgvector:pg16` 再部署，迁移会**自动**建向量列+扩展+索引，**无需手工 DDL**。见 [四] |
| **B. 已有生产库**（一直用 `postgres:16-alpine`，迁移 `ai01c2d3e4f5` 当时是在无 pgvector 环境执行的） | 库里已有业务数据；执行下方「自检」命令返回 `无` | 按 [三] 计划内维护流程：换镜像 + REINDEX + 手工补建向量列。**这是最常见的情况。** |

**自检命令**（在部署目录执行，判断向量列是否已存在）：
```bash
docker compose exec -T db psql -U postgres -d spt_crm -tAc \
  "SELECT COALESCE((SELECT 'has-vector' FROM pg_extension WHERE extname='vector'),'无 pgvector 扩展');
   SELECT COALESCE((SELECT 'has-column' FROM information_schema.columns
     WHERE table_name='knowledge_chunks' AND column_name='embedding'),'无 embedding 列');"
```
- 两行都返回 `无…` → 情况 B，按 [三] 升级。
- 都返回 `has-…` → 已经是 pgvector，无需操作，只差在「系统设置→AI模型」里配置嵌入模型即可。

---

## 二、关键风险与前置准备（务必先读）

1. **停机**：换 db 镜像需要重建数据库容器，有 **几分钟停机**（433MB 库约 1–3 分钟）。请安排在低峰维护窗口。
2. **collation 风险（最重要）**：`postgres:16-alpine` 用 **musl** libc，`pgvector/pgvector:pg16` 用 **glibc**。两者的 `en_US.utf8` 排序规则实现**不同**，同数据卷直接换镜像后，**文本类索引可能排序错乱**（查询漏行）。
   → **对策：换镜像后、放开流量前，必须 `REINDEX DATABASE` 重建全部索引。** 本流程已包含该步。
3. **务必先备份**：`pg_dump` 全库备份留底，出问题可回滚。
4. **镜像获取**：生产内网通常拉不到 Docker Hub。需先把 `pgvector/pgvector:pg16` 弄到目标服务器，二选一：
   - **私有 Harbor（推荐，CI 已支持）**：本项目 CI 会把镜像转推到 `wmharbor.fourier.net.cn:39011/hengchao-dev/pgvector:pg16`，服务器 `docker pull` 该地址即可。
   - **离线导入**：在有外网的机器上
     ```bash
     docker pull pgvector/pgvector:pg16
     docker save pgvector/pgvector:pg16 | gzip > pgvector-pg16.tar.gz
     ```
     scp 到目标服务器后 `gunzip -c pgvector-pg16.tar.gz | docker load`。

> 约定：下文 `docker compose` 命令都在**部署目录**执行（本项目生产为 `/home/hengchao/ai-crm`，其它服务器按实际路径）。数据库名 `spt_crm`、用户 `postgres`、db 服务名 `db`、数据卷 `pgdata`。

---

## 三、情况 B：已有生产库的升级流程（同卷换镜像 + REINDEX）

> 全程约 5–10 分钟，停机约 1–3 分钟。**逐步执行、每步确认成功再继续。**

### 步骤 0：确保 pgvector 镜像已在本机
```bash
docker pull wmharbor.fourier.net.cn:39011/hengchao-dev/pgvector:pg16   # 或用离线 load
docker images | grep pgvector    # 确认存在
```

### 步骤 1：备份（app 仍在线时做，兜底）
```bash
TS=$(date +%F_%H%M%S)
docker compose exec -T db pg_dump -U postgres -Fc spt_crm > backup_pre_pgvector_$TS.dump
ls -lh backup_pre_pgvector_$TS.dump    # 确认文件非 0 字节
```

### 步骤 2：把 db 镜像改成 pgvector
编辑部署目录的 `docker-compose.yml`，把 `db` 服务的镜像行改为：
```yaml
  db:
    image: pgvector/pgvector:pg16          # 或私有 Harbor 地址
    # 其余(volumes: pgdata、environment、ports)保持不变
```
> 本仓库的 `docker-compose.prod.yml` 已经改好（指向 Harbor 地址），走 CI 自动部署的服务器会自动带上；手工部署的服务器需手工改这一行。**注意：`volumes` 仍用原来的 `pgdata`，不要改卷名，否则会变成空库。**

### 步骤 3：停应用写入方 → 重建 db（复用原数据卷）
```bash
docker compose stop backend worker reminder
docker compose up -d db
# 等就绪
for i in $(seq 1 30); do docker compose exec -T db pg_isready -U postgres && break; sleep 2; done
# 确认已是 glibc/Debian 版 PG16
docker compose exec -T db psql -U postgres -d spt_crm -tAc "select version();"
```

### 步骤 4：REINDEX（修复 musl→glibc 排序，**不可跳过**）
```bash
docker compose exec -T db psql -U postgres -d spt_crm -c "REINDEX DATABASE spt_crm;"
```

### 步骤 5：建向量扩展 + 列 + 索引（幂等，可重复执行）
```bash
docker compose exec -T db psql -U postgres -d spt_crm -c "
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024);
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding
  ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
"
```
> 这三条 SQL 与迁移 `ai01c2d3e4f5` 在「有 pgvector 环境」里自动执行的完全一致；因为该迁移当时已在无 pgvector 环境标记为已应用、不会再自动跑，所以这里手工补齐一次。**维度固定 1024，勿改**（前端/嵌入客户端统一按 1024 维）。

### 步骤 6：启动全部服务
```bash
docker compose up -d
```

### 步骤 7：**重启 frontend（重要，避免 502）**
手工重建了 backend 容器后，backend 会拿到新的容器 IP，而 nginx（frontend 容器）可能缓存了旧 IP，导致 **502 Bad Gateway**。
```bash
docker compose restart frontend
```
> 走 CI 自动部署时 frontend 每次都会一起重建，不会有这个问题；**仅手工只重建 backend/db 时**才需要这一步。

---

## 四、情况 A：全新部署（最简单）

新服务器首次部署时，只要 `docker-compose.yml` 的 db 镜像已经是 `pgvector/pgvector:pg16`，则：
- `alembic upgrade head` 会**自动**检测到 pgvector 可用，自动 `CREATE EXTENSION vector` + 建 `embedding vector(1024)` 列 + HNSW 索引。
- **无需**执行 [三] 里的手工 DDL，也无需 REINDEX（新库直接由 glibc initdb，无 collation 迁移问题）。

照常部署即可。

---

## 五、升级后验证

```bash
# 1) 结构：扩展 + 列 + 索引 都在
docker compose exec -T db psql -U postgres -d spt_crm -tAc "
SELECT 'ext='||count(*) FROM pg_extension WHERE extname='vector';
SELECT 'col='||count(*) FROM information_schema.columns WHERE table_name='knowledge_chunks' AND column_name='embedding';
SELECT 'idx='||count(*) FROM pg_indexes WHERE indexname='ix_knowledge_chunks_embedding';"
# 期望 ext=1 col=1 idx=1

# 2) 数据完好（随便点几个业务表计数，应与升级前一致）
docker compose exec -T db psql -U postgres -d spt_crm -tAc "SELECT 'customers='||count(*) FROM customers;"

# 3) 应用健康：浏览器登录一次，或 curl 登录接口应返回 200
```

### 启用语义检索（配置嵌入模型）
数据库升级只是**具备**了向量能力，还需在 **系统设置 → AI模型 → 向量嵌入模型** 里选供应商（如「通义 text-embedding」）、填 API Key、启用。之后：
- 新建/编辑知识库文档会自动生成向量；
- 老文档需要「重嵌一次」才可被语义检索到（编辑保存内容即触发，或让管理员批量重嵌）。
- 未配置嵌入模型时，知识库自动用关键词检索，不报错。

---

## 六、回滚

如果升级后异常，需要回到 `postgres:16-alpine`。**注意顺序**：删 `vector` 列/索引这一步必须在**还处于 pgvector 镜像时**做（DROP 依赖扩展库；换回 alpine 后没有 vector 库，既用不了该类型也删不掉）。

```bash
# 1) 仍在 pgvector 镜像上，先删向量索引与列（否则 alpine 下读写 knowledge_chunks 会报错）
docker compose exec -T db psql -U postgres -d spt_crm -c "
DROP INDEX IF EXISTS ix_knowledge_chunks_embedding;
ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding;"
```
2. 把 `docker-compose.yml` 的 db 镜像改回 `postgres:16-alpine`；
3. `docker compose up -d db` → 等就绪 → `REINDEX DATABASE spt_crm;`（再次回到 musl 排序）；
4. `docker compose up -d && docker compose restart frontend`。

> 若已错换到 alpine 且 knowledge_chunks 读写报错、又删不掉列，用步骤 1 的 `pg_dump` 备份恢复到一个**全新 alpine 卷**（`docker compose down`、删旧卷、`up`、`pg_restore` 备份）。这也是最稳妥的兜底。

---

## 七、常见问题（FAQ）

- **换镜像后所有页面 502？** → nginx 缓存了旧 backend IP。`docker compose restart frontend`（见 [三] 步骤 7）。
- **升级后查询结果诡异/漏数据？** → 多半是漏了 REINDEX（collation 未重建）。补执行 `REINDEX DATABASE spt_crm;`。
- **`ERROR: type "vector" does not exist`** → db 镜像还是 alpine（没换成 pgvector），或 `CREATE EXTENSION vector` 没执行。
- **`could not open extension control file .../vector.control`** → 当前 db 镜像不带 pgvector，确认镜像确实是 `pgvector/pgvector:pg16`。
- **知识库搜不到语义相关内容？** → 检查「系统设置→AI模型」是否配了嵌入模型并启用；老文档是否已重嵌（有向量）。
- **数据卷会不会被清空？** → 只要 `volumes` 仍是原来的 `pgdata`、且不加 `-v` 删卷，数据不动。同为 PG16 主版本，磁盘格式兼容。

---

## 八、一句话总结

- **新服务器**：db 用 pgvector 镜像，正常部署，迁移自动搞定。
- **老服务器**：备份 → 换镜像 → `REINDEX DATABASE` → 建 vector 扩展/列/索引 → 起服务 →（手工重建时）重启 frontend → 到设置页配嵌入模型。
