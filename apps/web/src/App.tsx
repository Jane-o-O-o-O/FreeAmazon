import {
  AlertCircle,
  BadgeCheck,
  Boxes,
  CheckCircle2,
  CircleDollarSign,
  Factory,
  Gauge,
  ImageIcon,
  Link2,
  Loader2,
  PackageSearch,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Truck,
} from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import {
  AmazonProduct,
  RankedSourceItem,
  SourceSearchFilters,
  SourceSearchResult,
  SourceSearchTask,
  createSourceSearchTask,
  getSourceSearchResult,
} from "./api";

const exampleUrl = "https://www.amazon.com/dp/B0C1234567";

const statusText: Record<string, string> = {
  created: "已创建",
  fetching_amazon: "读取 Amazon",
  searching_1688: "搜索 1688",
  fetching_details: "补全详情",
  reranking: "相似度排序",
  completed: "已完成",
  failed: "失败",
};

export function App() {
  const [amazonUrl, setAmazonUrl] = useState(exampleUrl);
  const [marketplace, setMarketplace] = useState("US");
  const [filters, setFilters] = useState<SourceSearchFilters>({
    max_price_cny: null,
    factory_only: false,
    dropshipping: false,
    min_supplier_years: null,
  });
  const [task, setTask] = useState<SourceSearchTask | null>(null);
  const [result, setResult] = useState<SourceSearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setTask(null);
    setIsLoading(true);

    try {
      const created = await createSourceSearchTask({
        amazon_url: amazonUrl,
        marketplace,
        filters,
      });
      setTask(created);

      if (created.status === "failed") {
        setError(created.error_message ?? "任务执行失败");
        return;
      }

      const searchResult = await getSourceSearchResult(created.task_id);
      setResult(searchResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "未知错误");
    } finally {
      setIsLoading(false);
    }
  }

  const completedCount = result?.candidates.length ?? 0;
  const bestScore = result?.candidates[0]?.final_score ?? null;

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand-block">
          <div className="brand-mark">
            <PackageSearch size={22} />
          </div>
          <div>
            <strong>Amazon-Agent</strong>
            <span>跨平台找货源</span>
          </div>
        </div>

        <nav className="nav-list">
          <a className="nav-item active" href="#source-search">
            <Search size={18} />
            找相似货源
          </a>
          <a className="nav-item disabled" href="#history" aria-disabled="true">
            <Boxes size={18} />
            搜索记录
          </a>
          <a className="nav-item disabled" href="#risk" aria-disabled="true">
            <ShieldAlert size={18} />
            风险检测
          </a>
        </nav>

        <div className="sidebar-note">
          <span className="dot" />
          当前使用模拟数据源，可无密钥演示完整流程。
        </div>
      </aside>

      <section className="workspace" id="source-search">
        <header className="topbar">
          <div>
            <p className="eyebrow">选品与供应链匹配工作台</p>
            <h1>输入 Amazon 商品链接，自动匹配 1688 相似货源</h1>
            <p className="page-subtitle">
              系统会提取 Amazon 商品图和标题，搜索 1688 候选商品，并按图片相似度、价格、起订量和供应商质量排序。
            </p>
          </div>
          <div className="provider-pill">
            <span className="dot" />
            Canopy / TMAPI Mock
          </div>
        </header>

        <form className="search-panel" onSubmit={submit}>
          <div className="field-group url-field">
            <label htmlFor="amazon-url">Amazon 商品链接或 ASIN</label>
            <div className="input-with-icon">
              <Link2 size={18} />
              <input
                id="amazon-url"
                value={amazonUrl}
                onChange={(event) => setAmazonUrl(event.target.value)}
                placeholder={exampleUrl}
              />
            </div>
          </div>

          <div className="field-group market-field">
            <label htmlFor="marketplace">站点</label>
            <select
              id="marketplace"
              value={marketplace}
              onChange={(event) => setMarketplace(event.target.value)}
            >
              <option value="US">美国站</option>
              <option value="UK">英国站</option>
              <option value="DE">德国站</option>
              <option value="JP">日本站</option>
            </select>
          </div>

          <button className="primary-button" disabled={isLoading}>
            {isLoading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            {isLoading ? "匹配中" : "开始找货"}
          </button>

          <div className="filters" aria-label="筛选条件">
            <div className="filters-title">
              <SlidersHorizontal size={17} />
              采购筛选
            </div>
            <label className="compact-input">
              最高单价
              <input
                type="number"
                min="0"
                value={filters.max_price_cny ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    max_price_cny: event.target.value ? Number(event.target.value) : null,
                  }))
                }
                placeholder="元"
              />
            </label>
            <label className="compact-input">
              店铺年限
              <input
                type="number"
                min="0"
                value={filters.min_supplier_years ?? ""}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    min_supplier_years: event.target.value ? Number(event.target.value) : null,
                  }))
                }
                placeholder="年"
              />
            </label>
            <label className="switch-row">
              <input
                type="checkbox"
                checked={filters.factory_only}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    factory_only: event.target.checked,
                  }))
                }
              />
              <span>只看工厂</span>
            </label>
            <label className="switch-row">
              <input
                type="checkbox"
                checked={filters.dropshipping}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    dropshipping: event.target.checked,
                  }))
                }
              />
              <span>支持代发</span>
            </label>
          </div>
        </form>

        {error ? (
          <div className="error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        ) : null}

        <OverviewStrip task={task} count={completedCount} bestScore={bestScore} />

        {result ? (
          <section className="result-grid">
            <AmazonProductPanel product={result.amazon_product} />
            <CandidatePanel candidates={result.candidates} />
          </section>
        ) : (
          <EmptyState isLoading={isLoading} />
        )}
      </section>
    </main>
  );
}

function OverviewStrip({
  task,
  count,
  bestScore,
}: {
  task: SourceSearchTask | null;
  count: number;
  bestScore: number | null;
}) {
  return (
    <section className="overview-strip" aria-label="任务概览">
      <SummaryCard
        icon={<Gauge size={18} />}
        label="任务状态"
        value={task ? statusText[task.status] ?? task.status : "待开始"}
        hint={task?.message ?? "输入链接后自动执行"}
      />
      <SummaryCard
        icon={<Boxes size={18} />}
        label="候选货源"
        value={`${count} 条`}
        hint="图片搜索与关键词搜索合并"
      />
      <SummaryCard
        icon={<CheckCircle2 size={18} />}
        label="最高匹配"
        value={bestScore == null ? "-" : toPercent(bestScore)}
        hint="综合图片、标题和供应商评分"
      />
      <SummaryCard
        icon={<CircleDollarSign size={18} />}
        label="采购侧重点"
        value="低 MOQ"
        hint="优先展示小批量友好供应商"
      />
    </section>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <article className="summary-card">
      <div className="summary-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <p>{hint}</p>
      </div>
    </article>
  );
}

function AmazonProductPanel({ product }: { product: AmazonProduct }) {
  return (
    <section className="panel amazon-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Amazon 原商品</p>
          <h2>{product.asin}</h2>
        </div>
        <span className="score-badge">{product.marketplace}</span>
      </div>

      <div className="image-frame">
        <img className="product-image" src={product.main_image_url} alt={product.title} />
      </div>

      <h3>{product.title}</h3>
      <div className="facts">
        <Fact label="品牌" value={product.brand ?? "-"} />
        <Fact label="类目" value={product.category ?? "-"} />
        <Fact
          label="售价"
          value={
            product.price != null ? `${product.currency ?? ""} ${product.price.toFixed(2)}` : "-"
          }
        />
        <Fact
          label="评价"
          value={
            product.rating != null
              ? `${product.rating.toFixed(1)} 分 / ${product.review_count ?? 0} 条`
              : "-"
          }
        />
      </div>
    </section>
  );
}

function CandidatePanel({ candidates }: { candidates: RankedSourceItem[] }) {
  const best = useMemo(() => candidates[0], [candidates]);

  return (
    <section className="panel candidate-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">1688 候选货源</p>
          <h2>{candidates.length} 条可比较结果</h2>
        </div>
        {best ? <span className="score-badge">最佳匹配 {toPercent(best.final_score)}</span> : null}
      </div>

      <div className="candidate-list">
        {candidates.map((candidate, index) => (
          <CandidateCard key={candidate.item_id} candidate={candidate} rank={index + 1} />
        ))}
      </div>
    </section>
  );
}

function CandidateCard({ candidate, rank }: { candidate: RankedSourceItem; rank: number }) {
  return (
    <article className="candidate-card">
      <div className="candidate-media">
        <span className="rank-badge">#{rank}</span>
        <img src={candidate.image_url} alt={candidate.title} />
      </div>
      <div className="candidate-body">
        <div className="candidate-title-row">
          <div>
            <h3>{candidate.title}</h3>
            <p className="item-id">1688 商品 ID：{candidate.item_id}</p>
          </div>
          <span className={candidate.final_score >= 0.72 ? "match strong" : "match"}>
            {localizeMatchLabel(candidate.match_label)}
          </span>
        </div>

        <div className="metric-grid">
          <Metric label="综合评分" value={toPercent(candidate.final_score)} />
          <Metric label="图片相似" value={toPercent(candidate.image_similarity)} />
          <Metric
            label="采购价"
            value={candidate.price_min != null ? `¥${candidate.price_min.toFixed(1)}` : "-"}
          />
          <Metric label="起订量" value={`${candidate.moq ?? "-"} 件`} />
          <Metric label="月销参考" value={`${candidate.monthly_sales ?? "-"} 件`} />
          <Metric label="供应商评分" value={toPercent(candidate.supplier_score)} />
        </div>

        <div className="supplier-row">
          <span>
            <Boxes size={15} />
            {candidate.supplier_name ?? "-"}
          </span>
          <span>
            <Truck size={15} />
            {candidate.supplier_location ?? "-"}
          </span>
          {candidate.supplier_years ? <span>{candidate.supplier_years} 年店铺</span> : null}
          {candidate.is_factory ? (
            <span className="tag-positive">
              <Factory size={15} />
              工厂
            </span>
          ) : null}
          {candidate.supports_dropshipping ? (
            <span className="tag-positive">
              <BadgeCheck size={15} />
              支持代发
            </span>
          ) : null}
        </div>

        <p className="explanation">{candidate.explanation}</p>
      </div>
    </article>
  );
}

function EmptyState({ isLoading }: { isLoading: boolean }) {
  return (
    <section className="empty-state">
      {isLoading ? <Loader2 className="spin" size={30} /> : <ImageIcon size={30} />}
      <h2>{isLoading ? "正在匹配国内货源" : "等待输入第一个 Amazon 商品链接"}</h2>
      <p>
        第一版已经跑通完整的模拟链路。后续只需要把 Canopy API、TMAPI 和 CLIP 服务替换为真实实现。
      </p>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function toPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function localizeMatchLabel(label: string) {
  if (label === "疑似同款" || label === "相似款" || label === "低可信") return label;
  if (label === "Likely same item") return "疑似同款";
  if (label === "Similar item") return "相似款";
  if (label === "Low confidence") return "低可信";
  return label;
}
