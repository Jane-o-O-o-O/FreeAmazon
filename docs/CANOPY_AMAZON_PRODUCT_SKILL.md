# Canopy Amazon 商品信息 Skill

## 目标

Canopy 是本项目的 Amazon 商品数据获取源。输入 Amazon URL 或 ASIN 后，后端通过 Canopy REST API 获取商品标题、品牌、价格、评分、评论数、主图和类目，并归一化为项目内部的 `AmazonProduct`。

## 官方接口

- 文档入口：https://docs.canopyapi.co/
- REST OpenAPI：https://rest.canopyapi.co/api/v1/openapi.json
- REST Base URL：`https://rest.canopyapi.co`
- 商品详情：`GET /api/amazon/product`
- 认证方式：请求头 `API-KEY: <CANOPY_API_KEY>`

商品详情支持参数：

| 参数 | 说明 |
| --- | --- |
| `asin` | Amazon ASIN，例如 `B01HY0JA3G` |
| `url` | Amazon 商品 URL |
| `gtin` | ISBN、UPC 或 EAN |
| `domain` | 站点区域，默认 `US`，可用值包括 `US`、`UK`、`CA`、`DE`、`FR`、`IT`、`ES`、`AU`、`IN`、`MX`、`BR`、`JP`、`PL` |

## 当前代码位置

- REST 客户端：`apps/api/app/services/canopy_client.py`
- Amazon 业务封装：`apps/api/app/services/amazon_service.py`
- 配置：`apps/api/app/core/config.py`
- 搜源入口：`POST /api/source-search/tasks`

## 环境变量

```env
CANOPY_API_KEY=你的 Canopy API Key
CANOPY_API_BASE_URL=https://rest.canopyapi.co
CANOPY_TIMEOUT_SECONDS=30
CANOPY_USE_MOCK=false
```

默认 `CANOPY_USE_MOCK=true`，方便没有 Key 时继续开发前端、1688 搜索和相似度排序。

## 归一化字段

| Canopy 字段 | 项目字段 |
| --- | --- |
| `data.amazonProduct.asin` | `AmazonProduct.asin` |
| `title` | `title` |
| `brand` | `brand` |
| `url` | `url` |
| `price.value` | `price` |
| `price.currency` | `currency` |
| `rating` | `rating` |
| `ratingsTotal` | `review_count` |
| `mainImageUrl` | `main_image_url` |
| `imageUrls` | `image_urls` |
| `categories[].breadcrumbPath` 或 `categories[].name` | `category` |

## 已封装的 Canopy 能力

`CanopyClient` 已预留完整 Amazon REST wrapper，后续可直接用于竞品分析和市场监控：

- 商品详情：`get_product`
- 变体：`get_product_variants`
- 库存估算：`get_product_stock`
- 销量估算：`get_product_sales`
- 评论：`get_product_reviews`
- 报价：`get_product_offers`
- 搜索：`search_products`
- 搜索联想：`autocomplete`
- 类目树：`get_categories`
- 类目商品：`get_category`
- 卖家：`get_seller`
- 作者：`get_author`
- Deals：`get_deals`
- Best Sellers：`get_bestsellers`
- Best Seller 类目：`get_bestseller_categories`

## 错误策略

- 未配置 Key：抛出清晰错误，提示设置 `CANOPY_API_KEY` 或回到 mock 模式。
- HTTP 401/402/4xx/5xx：解析 Canopy `errors[].message` 并向任务错误信息透出。
- 超时：返回可读的超时错误。
- 响应缺少 `data.amazonProduct`：视为数据源异常，任务失败。

## MVP 调用链

```text
Amazon URL/ASIN
  -> AmazonService.parse_asin_from_url
  -> CanopyClient.get_product(asin, domain)
  -> AmazonService._product_from_canopy_payload
  -> Source1688Service.search_candidates
  -> RankingService.rank
```
