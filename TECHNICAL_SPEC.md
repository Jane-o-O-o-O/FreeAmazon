# Amazon-Agent 技术文档

更新时间：2026-06-14

## 1. 项目定位

Amazon-Agent 是一个面向跨境电商选品和找货源的 Web 系统。

核心目标：

用户输入一个 Amazon 商品链接，系统自动获取该商品的标题、主图、副图、价格、品牌、类目等信息，然后在 1688 等国内批发平台上寻找相似或同款商品，并通过图片相似度、标题相似度、价格、起订量、供应商质量等维度重新排序，最终输出一组可参考的国内货源。

一句话产品定义：

```text
Amazon 商品链接 -> Amazon 商品信息解析 -> 1688 以图搜货/关键词搜货 -> CLIP 相似度重排 -> 输出候选货源
```

## 2. 当前已确定的技术选择

### 2.1 Amazon 商品数据源

首选：Canopy API

当前落地：

- 后端已实现 Canopy REST 客户端：`apps/api/app/services/canopy_client.py`
- 商品详情已接入 `GET https://rest.canopyapi.co/api/amazon/product`
- 认证使用请求头 `API-KEY`
- 默认仍启用 mock 模式，设置 `CANOPY_USE_MOCK=false` 且配置 `CANOPY_API_KEY` 后走真实 Canopy 数据
- 项目内使用说明见 `docs/CANOPY_AMAZON_PRODUCT_SKILL.md`

用途：

- 根据 Amazon URL 或 ASIN 获取商品信息
- 获取标题、品牌、价格、评分、评论数、主图、副图、类目等字段
- 用作后续 1688 图片搜索和关键词搜索的输入

选择原因：

- 接入成本低
- 适合 MVP
- 不需要先申请 Amazon SP-API
- 比自建 Amazon 爬虫稳定

备选：

- Amazon SP-API：后期正式化可考虑，但需要 Amazon Professional Seller 账号，门槛更高
- ScraperAPI / Rainforest API / Oxylabs / Bright Data：作为后期备用 Amazon 数据源

### 2.2 1688 数据源

首选：TMAPI 1688 API

用途：

- 1688 图片搜索
- 1688 关键词搜索
- 1688 商品详情
- 价格阶梯、起订量、销量、SKU
- 店铺和供应商信息
- 工厂、认证供应商、代发能力等筛选

选择原因：

- API 化接入，比浏览器自动化更适合网站后端
- 能覆盖本项目 MVP 的主要数据需求
- 与 Canopy API 返回的 Amazon 图片 URL 可以形成完整链路

兜底：1688-cli

用途：

- MVP 调试和人工验证
- 当 TMAPI 字段不足或结果异常时做备用
- 作为浏览器登录态方式访问 1688

注意：

- 1688-cli 更像自动化工具，不适合作为高并发生产主链路
- 可能受到登录态、滑块、风控、页面结构变化影响

后期备用：

- Onebound 1688 API
- Oxylabs 1688 Scraper
- Apify 1688 Actor

### 2.3 相似度重排

首选：CLIP 本地模型

用途：

- 对 Amazon 主图/副图和 1688 候选商品图做视觉相似度计算
- 对 1688 搜索结果做二次排序
- 过滤明显不相关的候选商品

部署方式：

- MVP 阶段可使用 Python 服务单独运行
- 后期可做成独立 embedding/rerank 服务
- 图片向量可缓存到数据库，避免重复计算

### 2.4 推荐技术栈

后端：

- Python
- FastAPI
- Celery 或 RQ
- Redis

前端：

- Next.js 或 React
- Tailwind CSS 或现有 UI 组件库

数据库：

- PostgreSQL
- pgvector，可选，用于图片向量缓存和相似度查询

对象存储：

- 本地文件系统用于 MVP
- 后期可切换 S3、Cloudflare R2、阿里云 OSS

部署：

- Docker Compose
- 后期可拆为 API 服务、worker 服务、前端服务、数据库、Redis

## 3. MVP 范围

### 3.1 MVP 必须实现

1. 用户输入 Amazon 商品链接
2. 系统解析 ASIN
3. 调用 Canopy API 获取 Amazon 商品信息
4. 保存 Amazon 商品标题、图片、价格、品牌、类目
5. 调用 TMAPI 以 Amazon 主图进行 1688 图片搜索
6. 使用 Amazon 标题生成中文关键词，并调用 TMAPI 进行 1688 关键词搜索
7. 合并图片搜索和关键词搜索结果
8. 获取候选 1688 商品详情
9. 用 CLIP 计算 Amazon 图片与 1688 商品图片相似度
10. 生成综合评分并排序
11. 在前端展示候选货源列表

### 3.2 MVP 暂不实现

- 订单管理
- 库存管理
- 店铺授权
- 自动采购
- 自动上架
- 客服机器人
- 完整 ERP 功能
- 大规模监控任务
- 多租户计费系统

这些能力属于后续阶段，不进入第一版。

## 4. 核心业务流程

### 4.1 总流程

```text
用户输入 Amazon URL
  -> 后端解析 URL，提取 ASIN
  -> 调用 Canopy API 获取 Amazon 商品数据
  -> 下载或缓存 Amazon 主图/副图
  -> 调用 TMAPI 1688 图片搜索
  -> 将 Amazon 标题翻译/改写为中文关键词
  -> 调用 TMAPI 1688 关键词搜索
  -> 合并候选 1688 商品
  -> 调用 TMAPI 获取商品详情和供应商信息
  -> CLIP 计算图片相似度
  -> 计算综合评分
  -> 保存任务结果
  -> 前端展示结果
```

### 4.2 数据流

```text
Amazon URL
  -> ASIN
  -> Canopy API
  -> AmazonProduct
  -> ProductImage
  -> TMAPI image search
  -> TMAPI keyword search
  -> CandidateSourceItem
  -> CLIP rerank
  -> RankedSourceItem
```

## 5. 综合评分模型

MVP 默认评分：

```text
final_score =
  image_similarity * 0.45
  + title_similarity * 0.20
  + category_similarity * 0.10
  + price_score * 0.10
  + supplier_score * 0.10
  - risk_penalty * 0.05
```

### 5.1 图片相似度

来源：

- Amazon 主图
- Amazon 副图
- 1688 商品主图
- 1688 商品详情图，可选

方法：

- 使用 CLIP 提取 embedding
- 计算 cosine similarity
- 多图时取最高分或加权平均

建议：

- Amazon 主图权重最高
- 1688 主图优先
- 详情图在 MVP 中可以先不做

### 5.2 标题相似度

来源：

- Amazon 英文标题
- Amazon 标题翻译后的中文关键词
- 1688 中文标题

方法：

- 简单版：关键词重合度
- 进阶版：使用文本 embedding
- 后期可加 LLM 判断是否为同一产品类型

### 5.3 价格评分

考虑因素：

- 1688 单价是否明显低于 Amazon 售价
- 是否存在价格阶梯
- 是否满足合理毛利空间
- 起订量是否过高

MVP 中只做基本打分，不做完整跨境利润模型。

### 5.4 供应商评分

考虑因素：

- 是否工厂
- 是否实力商家
- 是否支持一件代发
- 店铺经营年限
- 回头率或交易数据
- 发货地
- 评分和服务指标

### 5.5 风险扣分

初版风险：

- 明显品牌词
- Amazon 商品疑似品牌私模
- 1688 商品图片带品牌 Logo
- 标题中出现商标词
- 相似度很高但价格异常低

后期可加入商标检索和侵权风险 Agent。

## 6. 页面设计

### 6.1 首页/任务页

功能：

- 输入 Amazon 商品链接
- 显示任务状态
- 展示最近搜索记录

输入：

- Amazon URL
- 可选：目标国家站点，例如 US、UK、DE、JP
- 可选：目标采购条件，例如最高采购价、是否只看工厂、是否支持一件代发

### 6.2 Amazon 商品概览

展示：

- 商品标题
- ASIN
- 商品主图
- 副图
- 品牌
- 类目
- Amazon 价格
- 评分和评论数
- 原始链接

### 6.3 1688 候选货源列表

每个候选商品展示：

- 1688 商品图
- 商品标题
- 单价
- 价格阶梯
- 起订量
- 供应商名称
- 供应商地区
- 店铺年限
- 是否工厂/实力商家
- 是否支持代发
- 图片相似度
- 综合评分
- 匹配判断：疑似同款、相似款、低相关
- 1688 链接

### 6.4 对比视图

展示：

- 左侧 Amazon 商品
- 右侧 1688 候选商品
- 图片并排对比
- 价格和供应链指标对比
- AI 解释为什么推荐或不推荐

## 7. 后端服务模块

### 7.1 amazon_service

职责：

- 解析 Amazon URL
- 提取 ASIN
- 调用 Canopy API
- 标准化 Amazon 商品数据

关键函数：

```python
parse_asin_from_url(url: str) -> str
fetch_amazon_product(asin: str, marketplace: str) -> AmazonProduct
normalize_canopy_response(raw: dict) -> AmazonProduct
```

### 7.2 source1688_service

职责：

- 调用 TMAPI 图片搜索
- 调用 TMAPI 关键词搜索
- 获取 1688 商品详情
- 获取供应商信息
- 标准化 1688 数据

关键函数：

```python
search_1688_by_image(image_url: str, filters: dict) -> list[SourceItem]
search_1688_by_keyword(keyword: str, filters: dict) -> list[SourceItem]
fetch_1688_item_detail(item_id: str) -> SourceItemDetail
fetch_1688_supplier(supplier_id: str) -> SupplierInfo
```

### 7.3 image_service

职责：

- 下载图片
- 图片去重
- 图片格式标准化
- 生成图片 hash
- 存储图片

关键函数：

```python
download_image(url: str) -> LocalImage
normalize_image(path: str) -> LocalImage
compute_image_hash(path: str) -> str
```

### 7.4 clip_service

职责：

- 加载 CLIP 模型
- 提取图片向量
- 计算图片相似度
- 缓存 embedding

关键函数：

```python
embed_image(path: str) -> list[float]
cosine_similarity(a: list[float], b: list[float]) -> float
rank_by_image_similarity(source_image: str, candidates: list[str]) -> list[RankedImage]
```

### 7.5 ranking_service

职责：

- 合并候选结果
- 去重
- 计算标题相似度
- 计算供应商评分
- 计算最终分数

关键函数：

```python
merge_candidates(image_results: list, keyword_results: list) -> list[Candidate]
score_candidate(amazon_product: AmazonProduct, candidate: Candidate) -> RankedCandidate
rank_candidates(candidates: list[Candidate]) -> list[RankedCandidate]
```

### 7.6 task_service

职责：

- 创建搜索任务
- 异步执行任务
- 记录任务状态
- 失败重试
- 返回任务结果

状态：

```text
created
fetching_amazon
searching_1688
fetching_details
reranking
completed
failed
```

## 8. API 设计草案

### 8.1 创建找货源任务

```http
POST /api/source-search/tasks
```

请求：

```json
{
  "amazon_url": "https://www.amazon.com/dp/B0XXXXXXX",
  "marketplace": "US",
  "filters": {
    "max_price_cny": 50,
    "factory_only": false,
    "dropshipping": false,
    "min_supplier_years": 1
  }
}
```

响应：

```json
{
  "task_id": "task_123",
  "status": "created"
}
```

### 8.2 查询任务状态

```http
GET /api/source-search/tasks/{task_id}
```

响应：

```json
{
  "task_id": "task_123",
  "status": "reranking",
  "progress": 70,
  "message": "正在计算图片相似度"
}
```

### 8.3 获取任务结果

```http
GET /api/source-search/tasks/{task_id}/results
```

响应：

```json
{
  "task_id": "task_123",
  "amazon_product": {
    "asin": "B0XXXXXXX",
    "title": "Amazon product title",
    "brand": "Brand",
    "price": 29.99,
    "currency": "USD",
    "main_image_url": "https://..."
  },
  "candidates": [
    {
      "source": "1688",
      "item_id": "123456",
      "title": "1688 商品标题",
      "url": "https://detail.1688.com/offer/123456.html",
      "image_url": "https://...",
      "price_cny": 18.5,
      "moq": 2,
      "supplier_name": "某某工厂",
      "supplier_location": "广东 深圳",
      "image_similarity": 0.88,
      "final_score": 0.82,
      "match_label": "疑似同款"
    }
  ]
}
```

## 9. 数据库设计草案

### 9.1 source_search_tasks

```sql
CREATE TABLE source_search_tasks (
  id UUID PRIMARY KEY,
  amazon_url TEXT NOT NULL,
  asin TEXT,
  marketplace TEXT NOT NULL DEFAULT 'US',
  status TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  filters JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 9.2 amazon_products

```sql
CREATE TABLE amazon_products (
  id UUID PRIMARY KEY,
  asin TEXT NOT NULL,
  marketplace TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  brand TEXT,
  category TEXT,
  price NUMERIC,
  currency TEXT,
  rating NUMERIC,
  review_count INTEGER,
  main_image_url TEXT,
  raw_data JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (asin, marketplace)
);
```

### 9.3 product_images

```sql
CREATE TABLE product_images (
  id UUID PRIMARY KEY,
  owner_type TEXT NOT NULL,
  owner_id UUID NOT NULL,
  source_url TEXT NOT NULL,
  local_path TEXT,
  image_hash TEXT,
  embedding vector,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

说明：

- 如果暂不启用 pgvector，可以先把 embedding 存为 JSONB 或不入库
- MVP 可以先只存图片 URL 和本地路径

### 9.4 source_items

```sql
CREATE TABLE source_items (
  id UUID PRIMARY KEY,
  platform TEXT NOT NULL DEFAULT '1688',
  item_id TEXT NOT NULL,
  url TEXT,
  title TEXT,
  image_url TEXT,
  price_min NUMERIC,
  price_max NUMERIC,
  moq INTEGER,
  monthly_sales INTEGER,
  supplier_id TEXT,
  supplier_name TEXT,
  supplier_location TEXT,
  supplier_years INTEGER,
  is_factory BOOLEAN,
  supports_dropshipping BOOLEAN,
  raw_data JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (platform, item_id)
);
```

### 9.5 source_search_results

```sql
CREATE TABLE source_search_results (
  id UUID PRIMARY KEY,
  task_id UUID NOT NULL REFERENCES source_search_tasks(id),
  amazon_product_id UUID NOT NULL REFERENCES amazon_products(id),
  source_item_id UUID NOT NULL REFERENCES source_items(id),
  image_similarity NUMERIC,
  title_similarity NUMERIC,
  category_similarity NUMERIC,
  price_score NUMERIC,
  supplier_score NUMERIC,
  risk_penalty NUMERIC,
  final_score NUMERIC,
  match_label TEXT,
  explanation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 10. 环境变量草案

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/amazon_agent
REDIS_URL=redis://localhost:6379/0

CANOPY_API_KEY=
CANOPY_API_BASE_URL=

TMAPI_KEY=
TMAPI_BASE_URL=

IMAGE_STORAGE_DIR=./storage/images

CLIP_MODEL_NAME=ViT-B/32

APP_ENV=development
LOG_LEVEL=info
```

## 11. 错误处理策略

### 11.1 Amazon 数据失败

可能原因：

- URL 无法解析 ASIN
- Canopy API 返回为空
- 商品不可用或地区不匹配
- API key 错误或余额不足

处理：

- 标记任务 failed
- 保存原始错误
- 前端展示明确原因
- 允许用户上传商品图作为 fallback

### 11.2 1688 搜索失败

可能原因：

- TMAPI 调用失败
- 图片 URL 无法访问
- 1688 没有相似结果
- 接口限流

处理：

- 先重试
- 图片搜索失败时尝试关键词搜索
- 主数据源失败时尝试 1688-cli 兜底

### 11.3 CLIP 重排失败

可能原因：

- 图片下载失败
- 图片格式异常
- 模型加载失败
- GPU/CPU 资源不足

处理：

- 不阻断任务
- 若 CLIP 失败，先用 1688 API 原始排序返回
- 标记结果为未重排

## 12. 合规和风控注意事项

### 12.1 Amazon

当前选择 Canopy API 作为 Amazon 商品数据源。

注意：

- Canopy API 是第三方商品数据 API，不是 Amazon 官方接口
- 正式商用前需要确认服务条款
- 不要在系统中宣称数据来自 Amazon 官方 API
- 只保存业务必要字段，避免无意义大规模抓取

### 12.2 1688

当前选择 TMAPI 作为 1688 主数据源。

注意：

- 1688 数据接口可能存在字段变化、价格变化、登录风控
- 正式商用前需要评估 TMAPI 的稳定性和服务条款
- 1688-cli 只作为调试和备用，不作为高并发主链路

### 12.3 侵权风险

系统只是帮助寻找相似货源，不代表可以直接销售。

后期应加入：

- 品牌词检测
- 商标风险检测
- 图片 Logo 检测
- Listing 文案侵权提示
- 专利和外观风险人工复核流程

## 13. 开发里程碑

### 阶段 0：项目脚手架

目标：

- 初始化项目结构
- 配置 Docker Compose
- 启动 FastAPI、前端、PostgreSQL、Redis
- 建立基础配置和日志

产出：

- 可运行的本地开发环境
- 健康检查接口

### 阶段 1：Amazon 数据获取

目标：

- 实现 Amazon URL 解析 ASIN
- 接入 Canopy API
- 保存 Amazon 商品数据
- 前端展示 Amazon 商品概览

验收：

- 输入 Amazon URL 后能看到标题、主图、价格、品牌等信息

### 阶段 2：1688 图片搜索

目标：

- 接入 TMAPI 图片搜索
- 使用 Amazon 主图搜索 1688 商品
- 保存候选商品基础数据
- 前端展示候选列表

验收：

- 输入 Amazon URL 后能看到一组 1688 候选商品

### 阶段 3：详情补全和供应商信息

目标：

- 获取 1688 商品详情
- 获取价格阶梯、MOQ、供应商信息
- 增加基础筛选条件

验收：

- 候选列表中包含价格、起订量、供应商、地区、是否工厂等信息

### 阶段 4：CLIP 相似度重排

目标：

- 部署 CLIP 服务
- 下载图片并计算 embedding
- 对候选商品做图片相似度排序

验收：

- 候选列表按相似度和综合评分排序
- 明显不相关商品可以被降权

### 阶段 5：综合评分和解释

目标：

- 实现综合评分模型
- 输出匹配标签
- 输出 AI 风格的推荐理由

验收：

- 每个候选商品显示最终评分、匹配判断和简短解释

## 14. 推荐项目结构

```text
E:\Amazon-Agent
  apps
    api
      app
        main.py
        core
        services
        models
        schemas
        tasks
        db
      tests
      pyproject.toml
    web
      app
      components
      lib
      package.json
  docker-compose.yml
  .env.example
  TECHNICAL_SPEC.md
  README.md
```

## 15. 后续开发约定

1. 优先实现可运行 MVP，不先做大而全系统
2. 所有外部 API 响应都要保存 raw_data，方便排查字段变化
3. Canopy API 和 TMAPI 必须封装在独立 service 中，方便替换供应商
4. 搜索任务必须异步执行，避免前端长时间等待
5. 每个任务都要保存状态和错误信息
6. 图片下载、向量计算、详情补全都要可重试
7. 重排逻辑要可配置权重，后期方便调参
8. 不把 1688-cli 作为默认生产链路，只作为兜底和验证工具
9. 所有密钥只放环境变量，不写进代码仓库
10. 每完成一个阶段都要补充 README 和基础测试

## 16. 当前最终方案

当前项目的 MVP 技术路线确定为：

```text
Amazon 数据源：Canopy API
1688 主数据源：TMAPI
1688 兜底：1688-cli
相似度重排：CLIP 本地模型
后端：FastAPI
前端：Next.js 或 React
数据库：PostgreSQL
任务队列：Redis + Celery/RQ
部署：Docker Compose
```

第一版的核心成功标准：

```text
输入一个 Amazon 商品链接后，系统能自动返回一批 1688 相似货源，并按可信相似度排序。
```
