import {
  AlertCircle,
  BadgeCheck,
  Boxes,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleDollarSign,
  Database,
  Factory,
  FileText,
  Gauge,
  ImageIcon,
  Link2,
  Loader2,
  PackageSearch,
  Search,
  History,
  ListChecks,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Truck,
  Workflow,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AmazonProduct,
  CopywritingResult,
  RankedSourceItem,
  SourceSearchFilters,
  SourceSearchResult,
  SourceSearchTask,
  createSourceSearchTask,
  generateCopywriting,
  getSourceSearchResult,
  getSourceSearchTask,
  proxiedImageUrl,
} from "./api";

const inputPlaceholder = "输入链接";

const statusText: Record<string, string> = {
  created: "已创建",
  fetching_amazon: "获取链接商品",
  searching_1688: "搜索候选货源",
  fetching_details: "补全详情",
  reranking: "相似度排序",
  completed: "已完成",
  failed: "失败",
};

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const historyStorageKey = "amazon-agent-search-history";
const maxHistoryEntries = 50;
const candidatesPerPage = 4;

type ActiveView = "search" | "history" | "copywriting";

type CopywritingForm = {
  site: string;
  product_name: string;
  audience: string;
  selling_points: string;
  keywords: string;
  tone: string;
  language: string;
};

const copywritingSites = [
  { label: "Amazon", value: "amazon" },
  { label: "TikTok Shop", value: "tiktok" },
  { label: "Shopee", value: "shopee" },
  { label: "Lazada", value: "lazada" },
  { label: "eBay", value: "ebay" },
  { label: "独立站", value: "shopify" },
];

const workflowSteps = [
  { key: "amazon", label: "链接解析", hint: "读取源商品" },
  { key: "keyword", label: "关键词生成", hint: "提取中文搜源词" },
  { key: "source", label: "1688 搜源", hint: "合并候选商品" },
  { key: "rank", label: "相似度排序", hint: "生成推荐结果" },
];

type SearchHistoryEntry = {
  task_id: string;
  amazon_url: string;
  status: string;
  message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  asin?: string;
  marketplace?: string;
  title?: string;
  brand?: string | null;
  category?: string | null;
  price?: number | null;
  currency?: string | null;
  candidate_count?: number;
  best_score?: number | null;
};

function loadSearchHistory() {
  try {
    const raw = window.localStorage.getItem(historyStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry): entry is SearchHistoryEntry => {
        return (
          typeof entry === "object" &&
          entry !== null &&
          typeof entry.task_id === "string" &&
          typeof entry.amazon_url === "string"
        );
      })
      .slice(0, maxHistoryEntries);
  } catch {
    return [];
  }
}

function saveSearchHistory(entries: SearchHistoryEntry[]) {
  window.localStorage.setItem(historyStorageKey, JSON.stringify(entries.slice(0, maxHistoryEntries)));
}

function compactEntryUpdate(entry: Partial<SearchHistoryEntry> & { task_id: string }) {
  return Object.fromEntries(
    Object.entries(entry).filter(([, value]) => value !== undefined),
  ) as Partial<SearchHistoryEntry> & { task_id: string };
}

export function App() {
  const [activeView, setActiveView] = useState<ActiveView>("search");
  const [amazonUrl, setAmazonUrl] = useState("");
  const [filters, setFilters] = useState<SourceSearchFilters>({
    max_price_cny: null,
    max_moq: null,
    factory_only: false,
    dropshipping: false,
    min_supplier_years: null,
  });
  const [task, setTask] = useState<SourceSearchTask | null>(null);
  const [result, setResult] = useState<SourceSearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState<SearchHistoryEntry[]>(() => loadSearchHistory());
  const [copywritingForm, setCopywritingForm] = useState<CopywritingForm>({
    site: "amazon",
    product_name: "",
    audience: "",
    selling_points: "",
    keywords: "",
    tone: "专业可信",
    language: "中文",
  });
  const [copywritingResult, setCopywritingResult] = useState<CopywritingResult | null>(null);
  const [copywritingError, setCopywritingError] = useState<string | null>(null);
  const [isCopywritingLoading, setIsCopywritingLoading] = useState(false);

  function upsertHistory(entry: Partial<SearchHistoryEntry> & { task_id: string }) {
    setHistory((current) => {
      const nextEntry = compactEntryUpdate(entry);
      const existing = current.find((item) => item.task_id === entry.task_id);
      if (!existing && !nextEntry.amazon_url) {
        return current;
      }
      const merged: SearchHistoryEntry = existing
        ? { ...existing, ...nextEntry }
        : {
            amazon_url: nextEntry.amazon_url ?? "",
            status: nextEntry.status ?? "created",
            ...nextEntry,
          };
      const next = [merged, ...current.filter((item) => item.task_id !== entry.task_id)].slice(
        0,
        maxHistoryEntries,
      );
      saveSearchHistory(next);
      return next;
    });
  }

  function clearHistory() {
    setHistory([]);
    saveSearchHistory([]);
  }

  async function openHistoryEntry(entry: SearchHistoryEntry) {
    setActiveView("search");
    setError(null);
    setAmazonUrl(entry.amazon_url);
    try {
      const currentTask = await getSourceSearchTask(entry.task_id);
      setTask(currentTask);
      upsertHistory({
        task_id: entry.task_id,
        status: currentTask.status,
        message: currentTask.message,
        updated_at: currentTask.updated_at,
      });

      const searchResult = await getSourceSearchResult(entry.task_id);
      if (searchResult) {
        setResult(searchResult);
        upsertHistory(historyEntryFromResult(entry.amazon_url, currentTask, searchResult));
      }
    } catch (caught) {
      setResult(null);
      setTask(null);
      setError(
        caught instanceof Error
          ? `这条记录暂时无法恢复：${caught.message}`
          : "这条记录暂时无法恢复",
      );
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setTask(null);
    setIsLoading(true);

    try {
      const created = await createSourceSearchTask({
        amazon_url: amazonUrl,
        filters,
      });
      setTask(created);
      upsertHistory({
        task_id: created.task_id,
        amazon_url: amazonUrl,
        status: created.status,
        message: created.message,
        created_at: created.created_at,
        updated_at: created.updated_at,
      });

      await pollTask(created.task_id, amazonUrl);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "未知错误");
    } finally {
      setIsLoading(false);
    }
  }

  async function submitCopywriting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCopywritingError(null);
    setIsCopywritingLoading(true);

    try {
      const generated = await generateCopywriting({
        site: copywritingForm.site,
        product_name: copywritingForm.product_name,
        audience: copywritingForm.audience || null,
        selling_points: copywritingForm.selling_points || null,
        keywords: copywritingForm.keywords || null,
        tone: copywritingForm.tone,
        language: copywritingForm.language,
      });
      setCopywritingResult(generated);
    } catch (caught) {
      setCopywritingError(caught instanceof Error ? caught.message : "文案生成失败");
    } finally {
      setIsCopywritingLoading(false);
    }
  }

  async function pollTask(taskId: string, sourceUrl: string) {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const currentTask = await getSourceSearchTask(taskId);
      setTask(currentTask);
      upsertHistory({
        task_id: taskId,
        amazon_url: sourceUrl,
        status: currentTask.status,
        message: currentTask.message,
        created_at: currentTask.created_at,
        updated_at: currentTask.updated_at,
      });

      try {
        const searchResult = await getSourceSearchResult(taskId);
        if (searchResult) {
          setResult(searchResult);
          upsertHistory(historyEntryFromResult(sourceUrl, currentTask, searchResult));
        }
      } catch (caught) {
        throw caught;
      }

      if (currentTask.status === "failed") {
        setError(currentTask.error_message ?? "任务执行失败");
        upsertHistory({
          task_id: taskId,
          amazon_url: sourceUrl,
          status: currentTask.status,
          message: currentTask.error_message ?? currentTask.message,
          updated_at: currentTask.updated_at,
        });
        return;
      }
      if (currentTask.status === "completed") {
        return;
      }
      await sleep(1000);
    }
    throw new Error("任务等待超时，请稍后重试");
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
          <button
            className={activeView === "search" ? "nav-item active" : "nav-item"}
            type="button"
            onClick={() => setActiveView("search")}
          >
            <Search size={18} />
            找相似货源
          </button>
          <button
            className={activeView === "history" ? "nav-item active" : "nav-item"}
            type="button"
            onClick={() => setActiveView("history")}
          >
            <History size={18} />
            搜索记录
          </button>
          <button
            className={activeView === "copywriting" ? "nav-item active" : "nav-item"}
            type="button"
            onClick={() => setActiveView("copywriting")}
          >
            <FileText size={18} />
            文案自动生成
          </button>
        </nav>

        <div className="sidebar-status" aria-label="系统连接状态">
          <p>系统状态</p>
          <span>
            <Database size={15} />
            Canopy 商品数据
          </span>
          <span>
            <Workflow size={15} />
            Apify 1688 搜源
          </span>
          <span>
            <Sparkles size={15} />
            SiliconFlow 文案
          </span>
        </div>

      </aside>

      {activeView === "search" ? (
        <SearchWorkspace
          amazonUrl={amazonUrl}
          bestScore={bestScore}
          completedCount={completedCount}
          error={error}
          filters={filters}
          isLoading={isLoading}
          result={result}
          setAmazonUrl={setAmazonUrl}
          setFilters={setFilters}
          submit={submit}
          task={task}
        />
      ) : activeView === "history" ? (
        <HistoryWorkspace
          entries={history}
          onClear={clearHistory}
          onOpen={openHistoryEntry}
          onSearchNew={() => setActiveView("search")}
        />
      ) : (
        <CopywritingWorkspace
          error={copywritingError}
          form={copywritingForm}
          historyEntries={history}
          isLoading={isCopywritingLoading}
          result={copywritingResult}
          setForm={setCopywritingForm}
          submit={submitCopywriting}
        />
      )}
    </main>
  );
}

function SearchWorkspace({
  amazonUrl,
  bestScore,
  completedCount,
  error,
  filters,
  isLoading,
  result,
  setAmazonUrl,
  setFilters,
  submit,
  task,
}: {
  amazonUrl: string;
  bestScore: number | null;
  completedCount: number;
  error: string | null;
  filters: SourceSearchFilters;
  isLoading: boolean;
  result: SourceSearchResult | null;
  setAmazonUrl: React.Dispatch<React.SetStateAction<string>>;
  setFilters: React.Dispatch<React.SetStateAction<SourceSearchFilters>>;
  submit: (event: FormEvent<HTMLFormElement>) => void;
  task: SourceSearchTask | null;
}) {
  return (
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
          生产链路：Canopy / Apify / SiliconFlow
        </div>
      </header>

      <WorkflowStrip task={task} />

      <form className="search-panel" onSubmit={submit}>
        <div className="search-panel-title">
          <div>
            <span>源商品输入</span>
            <small>支持 Amazon 商品链接与 ASIN，短链会自动解析</small>
          </div>
          <strong>{task ? statusText[task.status] ?? task.status : "待提交"}</strong>
        </div>

        <div className="field-group url-field">
          <label htmlFor="amazon-url">Amazon 商品链接或 ASIN</label>
          <div className="input-with-icon">
            <Link2 size={18} />
            <input
              id="amazon-url"
              value={amazonUrl}
              onChange={(event) => setAmazonUrl(event.target.value)}
              placeholder={inputPlaceholder}
            />
          </div>
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
            最高起订
            <input
              type="number"
              min="1"
              value={filters.max_moq ?? ""}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  max_moq: event.target.value ? Number(event.target.value) : null,
                }))
              }
              placeholder="件"
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
          <CandidatePanel candidates={result.candidates} isPartial={result.is_partial} />
        </section>
      ) : (
        <EmptyState isLoading={isLoading} task={task} />
      )}
    </section>
  );
}

function HistoryWorkspace({
  entries,
  onClear,
  onOpen,
  onSearchNew,
}: {
  entries: SearchHistoryEntry[];
  onClear: () => void;
  onOpen: (entry: SearchHistoryEntry) => void;
  onSearchNew: () => void;
}) {
  const completedEntries = entries.filter((entry) => entry.status === "completed").length;
  const totalCandidates = entries.reduce((sum, entry) => sum + (entry.candidate_count ?? 0), 0);

  return (
    <section className="workspace" id="history">
      <header className="topbar">
        <div>
          <p className="eyebrow">搜索记录</p>
          <h1>最近找过的 Amazon 商品</h1>
          <p className="page-subtitle">
            这里保存当前浏览器里的最近任务，方便回看原商品、候选数量和匹配结果。
          </p>
        </div>
        <div className="history-actions">
          {entries.length ? (
            <button className="secondary-button" type="button" onClick={onClear}>
              清空记录
            </button>
          ) : null}
          <button className="primary-button compact-button" type="button" onClick={onSearchNew}>
            <Search size={17} />
            新建搜索
          </button>
        </div>
      </header>

      {entries.length ? (
        <section className="history-overview" aria-label="搜索记录概览">
          <SummaryCard
            icon={<History size={18} />}
            label="历史任务"
            value={`${entries.length} 次`}
            hint="保存在当前浏览器"
          />
          <SummaryCard
            icon={<CheckCircle2 size={18} />}
            label="已完成"
            value={`${completedEntries} 次`}
            hint="可直接回看结果"
          />
          <SummaryCard
            icon={<Boxes size={18} />}
            label="累计候选"
            value={`${totalCandidates} 条`}
            hint="来自 1688 搜源结果"
          />
        </section>
      ) : null}

      {entries.length ? (
        <section className="history-list" aria-label="搜索记录列表">
          {entries.map((entry) => (
            <article className="history-card" key={entry.task_id}>
              <div>
                <div className="history-card-head">
                  <span className="score-badge">{statusText[entry.status] ?? entry.status}</span>
                  {entry.marketplace ? <span className="muted-pill">{entry.marketplace}</span> : null}
                  {entry.candidate_count != null ? (
                    <span className="muted-pill">{entry.candidate_count} 条候选</span>
                  ) : null}
                  {entry.best_score != null ? (
                    <span className="muted-pill">最高匹配 {toPercent(entry.best_score)}</span>
                  ) : null}
                </div>
                <h2>{entry.title ?? entry.asin ?? entry.amazon_url}</h2>
                <p className="history-url">{entry.amazon_url}</p>
                <p className="history-meta">
                  {formatDate(entry.updated_at ?? entry.created_at)} · {entry.message ?? "任务已记录"}
                </p>
              </div>
              <div className="history-card-actions">
                <button className="link-button button-link" type="button" onClick={() => onOpen(entry)}>
                  查看结果
                </button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="empty-state">
          <History size={30} />
          <h2>还没有搜索记录</h2>
          <p>完成一次找货后，这里会自动保存任务，之后可以从这里快速回看。</p>
        </section>
      )}
    </section>
  );
}

function CopywritingWorkspace({
  error,
  form,
  historyEntries,
  isLoading,
  result,
  setForm,
  submit,
}: {
  error: string | null;
  form: CopywritingForm;
  historyEntries: SearchHistoryEntry[];
  isLoading: boolean;
  result: CopywritingResult | null;
  setForm: React.Dispatch<React.SetStateAction<CopywritingForm>>;
  submit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const selectableEntries = historyEntries.filter((entry) => entry.title || entry.asin);

  function selectHistoryProduct(taskId: string) {
    const selected = selectableEntries.find((entry) => entry.task_id === taskId);
    if (!selected) return;

    const contextPoints = [
      selected.brand ? `品牌：${selected.brand}` : null,
      selected.category ? `类目：${selected.category}` : null,
      selected.price != null ? `Amazon 参考价：${selected.currency ?? ""} ${selected.price}` : null,
      selected.candidate_count != null ? `已匹配 ${selected.candidate_count} 条 1688 候选货源` : null,
    ].filter(Boolean);

    setForm((current) => ({
      ...current,
      product_name: selected.title ?? selected.asin ?? current.product_name,
      audience: current.audience || "跨境电商买家",
      selling_points: current.selling_points || contextPoints.join("\n"),
      keywords: mergeKeywords([
        selected.asin,
        selected.marketplace,
        selected.brand,
        selected.category,
        selected.title,
        current.keywords,
      ]),
    }));
  }

  return (
    <section className="workspace" id="copywriting">
      <header className="topbar">
        <div>
          <p className="eyebrow">文案自动生成</p>
          <h1>为不同站点生成上架文案</h1>
          <p className="page-subtitle">
            选择目标站点，输入商品名称、卖点和关键词，生成标题、卖点、描述和标签初稿。
          </p>
        </div>
        <div className="provider-pill">
          <span className="dot" />
          SiliconFlow AI 文案
        </div>
      </header>

      <section className="copywriting-grid">
        <form className="copywriting-form" onSubmit={submit}>
          <div className="form-section-title">
            <div>
              <span>生成配置</span>
              <small>选择站点、语气和商品信息后生成可编辑初稿</small>
            </div>
          </div>

          <div className="field-group">
            <label htmlFor="copy-site">目标站点</label>
            <select
              id="copy-site"
              value={form.site}
              onChange={(event) =>
                setForm((current) => ({ ...current, site: event.target.value }))
              }
            >
              {copywritingSites.map((site) => (
                <option key={site.value} value={site.value}>
                  {site.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label htmlFor="copy-history-product">从搜索历史选择商品</label>
            <select
              id="copy-history-product"
              value=""
              onChange={(event) => selectHistoryProduct(event.target.value)}
              disabled={!selectableEntries.length}
            >
              <option value="">
                {selectableEntries.length ? "选择历史商品" : "暂无可选择的历史商品"}
              </option>
              {selectableEntries.map((entry) => (
                <option key={entry.task_id} value={entry.task_id}>
                  {entry.title ?? entry.asin} {entry.marketplace ? `(${entry.marketplace})` : ""}
                </option>
              ))}
            </select>
            <p className="field-hint">选择后会使用历史商品信息填充名称、卖点和关键词。</p>
          </div>

          <div className="field-group">
            <label htmlFor="copy-product">商品名称</label>
            <input
              id="copy-product"
              value={form.product_name}
              onChange={(event) =>
                setForm((current) => ({ ...current, product_name: event.target.value }))
              }
              placeholder="例如：便携榨汁杯"
              required
            />
          </div>

          <div className="field-group">
            <label htmlFor="copy-audience">目标人群</label>
            <input
              id="copy-audience"
              value={form.audience}
              onChange={(event) =>
                setForm((current) => ({ ...current, audience: event.target.value }))
              }
              placeholder="例如：健身、通勤、户外人群"
            />
          </div>

          <div className="field-group">
            <label htmlFor="copy-points">核心卖点</label>
            <textarea
              id="copy-points"
              value={form.selling_points}
              onChange={(event) =>
                setForm((current) => ({ ...current, selling_points: event.target.value }))
              }
              placeholder="用逗号或换行分隔，例如：USB充电、小巧便携、易清洗"
            />
          </div>

          <div className="field-group">
            <label htmlFor="copy-keywords">搜索关键词</label>
            <textarea
              id="copy-keywords"
              value={form.keywords}
              onChange={(event) =>
                setForm((current) => ({ ...current, keywords: event.target.value }))
              }
              placeholder="例如：portable blender, smoothie cup, mini juicer"
            />
          </div>

          <div className="copywriting-row">
            <label className="field-group">
              语气
              <select
                value={form.tone}
                onChange={(event) =>
                  setForm((current) => ({ ...current, tone: event.target.value }))
                }
              >
                <option value="专业可信">专业可信</option>
                <option value="轻快直接">轻快直接</option>
                <option value="高端质感">高端质感</option>
                <option value="促销转化">促销转化</option>
              </select>
            </label>
            <label className="field-group">
              语言
              <select
                value={form.language}
                onChange={(event) =>
                  setForm((current) => ({ ...current, language: event.target.value }))
                }
              >
                <option value="中文">中文</option>
                <option value="英文">英文</option>
                <option value="中英双语">中英双语</option>
              </select>
            </label>
          </div>

          <button className="primary-button" disabled={isLoading}>
            {isLoading ? <Loader2 className="spin" size={18} /> : <FileText size={18} />}
            {isLoading ? "生成中" : "生成文案"}
          </button>
        </form>

        <section className="copywriting-result">
          <div className="copywriting-result-head">
            <div>
              <span>生成结果</span>
              <strong>{result ? result.site : "等待输入"}</strong>
            </div>
            <small>{result ? "已生成可编辑文案" : "标题、卖点、描述与关键词"}</small>
          </div>

          {error ? (
            <div className="error-banner">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          ) : null}

          {result ? (
            <div className="copywriting-output">
              <div className="copywriting-source">
                <span>{result.generation_source === "siliconflow" ? "硅基流动 AI" : "模板兜底"}</span>
                {result.model ? <strong>{result.model}</strong> : null}
                <small>{result.skill}</small>
              </div>
              <CopyBlock label="平台标题" value={result.title} />
              <CopyBlock label="短标题" value={result.short_title} />
              <div className="copy-block">
                <span>五点卖点</span>
                <ul>
                  {result.bullet_points.map((point) => (
                    <li key={point}>{point}</li>
                  ))}
                </ul>
              </div>
              <CopyBlock label="详情描述" value={result.description} />
              <CopyBlock label="标签" value={result.tags.join("，")} />
              <CopyBlock label="SEO 关键词" value={result.seo_keywords.join("，")} />
            </div>
          ) : (
            <div className="copywriting-placeholder">
              <FileText size={30} />
              <h2>等待生成第一组文案</h2>
              <p>建议先填商品名称和 3-5 个核心卖点，生成后再按目标站点微调。</p>
            </div>
          )}
        </section>
      </section>
    </section>
  );
}

function CopyBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="copy-block">
      <span>{label}</span>
      <p>{value}</p>
    </div>
  );
}

function WorkflowStrip({ task }: { task: SourceSearchTask | null }) {
  const activeIndex = workflowStepIndex(task?.status);
  const isCompleted = task?.status === "completed";

  return (
    <section className="workflow-strip" aria-label="找货处理流程">
      {workflowSteps.map((step, index) => {
        const stateClass =
          isCompleted || index < activeIndex ? "done" : index === activeIndex ? "active" : "";
        return (
          <article className={`workflow-step ${stateClass}`} key={step.key}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.label}</strong>
              <small>{step.hint}</small>
            </div>
          </article>
        );
      })}
    </section>
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
        hint="多关键词搜索结果合并"
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
        <div className="panel-actions">
          <span className="score-badge">{product.marketplace}</span>
          <a className="link-button" href={product.url} target="_blank" rel="noreferrer">
            <Link2 size={15} />
            打开原链接
          </a>
        </div>
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

function CandidatePanel({
  candidates,
  isPartial,
}: {
  candidates: RankedSourceItem[];
  isPartial: boolean;
}) {
  const best = useMemo(() => candidates[0], [candidates]);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(candidates.length / candidatesPerPage));
  const pageStart = (page - 1) * candidatesPerPage;
  const visibleCandidates = candidates.slice(pageStart, pageStart + candidatesPerPage);

  useEffect(() => {
    setPage(1);
    setIsCollapsed(false);
  }, [candidates]);

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  return (
    <section className={`panel candidate-panel${isCollapsed ? " is-collapsed" : ""}`}>
      <div className="panel-header">
        <div>
          <p className="eyebrow">1688 候选货源</p>
          <h2>{isPartial ? "正在搜索候选货源" : `${candidates.length} 条可比较结果`}</h2>
        </div>
        <div className="candidate-header-actions">
          {best ? <span className="score-badge">最佳匹配 {toPercent(best.final_score)}</span> : null}
          <button
            className="icon-button"
            type="button"
            onClick={() => setIsCollapsed((current) => !current)}
            aria-label={isCollapsed ? "展开候选货源" : "折叠候选货源"}
            title={isCollapsed ? "展开候选货源" : "折叠候选货源"}
          >
            {isCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
        </div>
      </div>

      {!isCollapsed ? (
        <>
          <div className="candidate-panel-tools">
            <span>
              <ImageIcon size={14} />
              图片相似
            </span>
            <span>
              <ListChecks size={14} />
              标题相关
            </span>
            <span>
              <CircleDollarSign size={14} />
              采购价格
            </span>
            <span>
              <ShieldCheck size={14} />
              供应商质量
            </span>
          </div>

          {candidates.length ? (
            <>
              <div className="candidate-list">
                {visibleCandidates.map((candidate, index) => (
                  <CandidateCard
                    key={candidate.item_id}
                    candidate={candidate}
                    rank={pageStart + index + 1}
                  />
                ))}
              </div>
              <div className="candidate-pagination" aria-label="候选货源分页">
                <span>
                  第 {page} / {totalPages} 页，每页 {candidatesPerPage} 个商品
                </span>
                <div>
                  <button
                    className="icon-button"
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    aria-label="上一页候选货源"
                    title="上一页"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <button
                    className="icon-button"
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    aria-label="下一页候选货源"
                    title="下一页"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="candidate-loading">
              <Loader2 className="spin" size={24} />
              <span>原商品已读取，正在匹配国内相似货源</span>
            </div>
          )}
        </>
      ) : (
        <div className="candidate-collapsed-summary">
          <span>{candidates.length ? `已收起 ${candidates.length} 条候选货源` : "候选货源区域已收起"}</span>
          {best ? <strong>当前最佳匹配 {toPercent(best.final_score)}</strong> : null}
        </div>
      )}
    </section>
  );
}

function CandidateCard({ candidate, rank }: { candidate: RankedSourceItem; rank: number }) {
  return (
    <article className="candidate-card">
      <div className="candidate-media">
        <span className="rank-badge">#{rank}</span>
        <img src={proxiedImageUrl(candidate.image_url)} alt={candidate.title} />
      </div>
      <div className="candidate-body">
        <div className="candidate-title-row">
          <div>
            <h3>{candidate.title}</h3>
          </div>
          <div className="candidate-actions">
            <a className="link-button" href={candidate.url} target="_blank" rel="noreferrer">
              <Link2 size={15} />
              打开商品
            </a>
          </div>
        </div>
        <p className="item-id">
          {candidate.source} 商品 ID：{candidate.item_id}
        </p>

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

function EmptyState({
  isLoading,
  task,
}: {
  isLoading: boolean;
  task: SourceSearchTask | null;
}) {
  const content = emptyStateContent(isLoading, task);

  return (
    <section className="empty-state">
      {isLoading ? <Loader2 className="spin" size={30} /> : <ImageIcon size={30} />}
      <h2>{content.title}</h2>
      <p>{content.description}</p>
    </section>
  );
}

function emptyStateContent(isLoading: boolean, task: SourceSearchTask | null) {
  if (!isLoading || !task) {
    return {
      title: "等待输入第一个 Amazon 商品链接",
      description: "当前已接入商品数据和搜源接口。输入链接后会读取 Amazon 商品并搜索相似货源。",
    };
  }

  if (task.status === "created" || task.status === "fetching_amazon") {
    return {
      title: "正在获取链接商品",
      description: "系统正在解析链接、识别站点，并读取 Amazon 原商品信息。",
    };
  }

  if (task.status === "searching_1688") {
    return {
      title: "原商品已读取，正在匹配候选货源",
      description: "系统正在根据商品标题、类目和中文关键词搜索 1688 相似供应来源。",
    };
  }

  if (task.status === "reranking") {
    return {
      title: "正在计算相似度并排序",
      description: "系统正在综合图片、标题、价格和供应商信息生成推荐排序。",
    };
  }

  return {
    title: "正在处理任务",
    description: task.message ?? "请稍等，系统正在继续处理当前任务。",
  };
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

function workflowStepIndex(status?: string | null) {
  if (!status || status === "created" || status === "fetching_amazon") return 0;
  if (status === "searching_1688" || status === "fetching_details") return 2;
  if (status === "reranking" || status === "completed") return 3;
  return 0;
}

function historyEntryFromResult(
  amazonUrl: string,
  task: SourceSearchTask,
  result: SourceSearchResult,
): SearchHistoryEntry {
  return {
    task_id: task.task_id,
    amazon_url: amazonUrl,
    status: task.status,
    message: task.message,
    created_at: task.created_at,
    updated_at: task.updated_at,
    asin: result.amazon_product.asin,
    marketplace: result.amazon_product.marketplace,
    title: result.amazon_product.title,
    brand: result.amazon_product.brand,
    category: result.amazon_product.category,
    price: result.amazon_product.price,
    currency: result.amazon_product.currency,
    candidate_count: result.candidates.length,
    best_score: result.candidates[0]?.final_score ?? null,
  };
}

function formatDate(value?: string | null) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function mergeKeywords(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const keywords: string[] = [];
  for (const value of values) {
    if (!value) continue;
    for (const item of value.split(/[,，、\n]/)) {
      const keyword = item.trim();
      if (!keyword || seen.has(keyword)) continue;
      seen.add(keyword);
      keywords.push(keyword);
    }
  }
  return keywords.join(", ");
}

function toPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}
