# AI News Bot - 优化任务清单

> 本文档列出了代码审查后发现的可优化项，按优先级排序

## 📊 优化概览

| 优先级 | 任务数 | 预计影响 |
|--------|--------|----------|
| 🔴 高优先级 | 3 | 性能提升 3-5x，质量显著改善 |
| 🟡 中优先级 | 3 | 可靠性和用户体验提升 |
| 🟢 低优先级 | 4 | 长期改进，增强可观测性 |

---

## 🔴 高优先级优化（立即实施）

### 1. 实现 RSS 源并发抓取

**影响**：⭐⭐⭐⭐⭐ | **难度**：🔧🔧 | **预计提升**：性能提升 3-5x

**当前问题**：
- 文件：`src/news/fetcher.py:275-306`
- 现状：串行抓取所有 RSS 源，20 个源需要 20-30 秒
- 影响：用户等待时间长，GitHub Actions 执行时间长

**优化方案**：
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_recent_news(self, language: str = "en", max_items_per_source: int = 5):
    all_news = {'international': [], 'domestic': []}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(self.fetch_rss_feed, url, max_items_per_source): name
            for name, url in self.rss_feeds.items()
        }

        for future in as_completed(futures):
            source_name = futures[future]
            try:
                items = future.result(timeout=15)
                for item in items:
                    item['source'] = source_name
                    all_news['international'].append(item)
            except Exception as e:
                logger.error(f"Failed to fetch {source_name}: {e}")
```

**验收标准**：
- [ ] 抓取时间从 30秒 降到 5-8秒
- [ ] 所有现有 RSS 源都能正常抓取
- [ ] 单个源失败不影响整体流程
- [ ] 日志正确记录每个源的状态

**预期收益**：
- 总执行时间减少 60-70%
- 用户体验显著提升
- GitHub Actions 配额使用减少

---

### 2. 添加新闻去重机制

**影响**：⭐⭐⭐⭐ | **难度**：🔧🔧 | **预计提升**：质量提升，token 节省 10-20%

**当前问题**：
- 文件：`src/news/generator.py`
- 现状：多个 RSS 源可能报道同一事件，导致重复内容
- 影响：AI 处理重复新闻浪费 token，最终摘要可能包含重复信息

**优化方案**：
```python
def _deduplicate_news(self, news_items: List[Dict]) -> List[Dict]:
    """使用标题相似度和链接去重"""
    from difflib import SequenceMatcher

    unique_news = []
    seen_links = set()

    for item in news_items:
        # 1. 链接去重
        if item['link'] in seen_links:
            continue

        # 2. 标题相似度去重
        is_duplicate = False
        for existing in unique_news:
            similarity = SequenceMatcher(
                None,
                item['title'].lower(),
                existing['title'].lower()
            ).ratio()

            if similarity > 0.85:  # 85% 相似度阈值
                is_duplicate = True
                # 保留描述更详细的版本
                if len(item.get('description', '')) > len(existing.get('description', '')):
                    unique_news.remove(existing)
                    unique_news.append(item)
                break

        if not is_duplicate:
            unique_news.append(item)
            seen_links.add(item['link'])

    logger.info(f"Deduplication: {len(news_items)} → {len(unique_news)} items")
    return unique_news
```

**实现位置**：
在 `generator.py` 的 `generate_news_digest_from_sources` 方法中，`fetch_recent_news` 之后、格式化新闻之前调用

**验收标准**：
- [ ] 相同链接的新闻只保留一条
- [ ] 标题高度相似（>85%）的新闻只保留描述更详细的
- [ ] 日志输出去重前后的数量对比
- [ ] 不误删不同的新闻

**预期收益**：
- 提高新闻摘要质量
- 减少 10-20% 的 LLM token 消耗
- 避免用户看到重复内容

---

### 3. 实现 RSS 请求重试机制

**影响**：⭐⭐⭐⭐ | **难度**：🔧 | **预计提升**：成功率提升 15-30%

**当前问题**：
- 文件：`src/news/fetcher.py:200`
- 现状：网络请求失败后直接跳过该源，无重试
- 影响：临时网络问题导致丢失重要新闻源

**优化方案**（二选一）：

**方案 A：使用 tenacity 库**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def fetch_rss_feed(self, feed_url: str, max_items: int = 10):
    # 现有代码...
```

**方案 B：手动实现**
```python
def fetch_rss_feed_with_retry(self, feed_url: str, max_items: int = 10, retries: int = 3):
    for attempt in range(retries):
        try:
            return self.fetch_rss_feed(feed_url, max_items)
        except Exception as e:
            if attempt == retries - 1:
                logger.error(f"All {retries} attempts failed for {feed_url}")
                return []
            logger.warning(f"Attempt {attempt + 1} failed, retrying...")
            time.sleep(2 ** attempt)  # 指数退避：2秒、4秒、8秒
```

**验收标准**：
- [ ] 临时网络错误会自动重试
- [ ] 使用指数退避策略
- [ ] 最多重试 3 次
- [ ] 日志记录重试次数和最终结果

**依赖**：
建议先完成"实现 RSS 源并发抓取"任务

**预期收益**：
- 提高 RSS 抓取成功率 15-30%
- 减少因临时网络问题导致的数据丢失

---

## 🟡 中优先级优化（近期实施）

### 4. 添加 RSS 抓取缓存机制

**影响**：⭐⭐⭐ | **难度**：🔧🔧🔧 | **预计提升**：开发调试速度 10x

**当前问题**：
- 每次运行都重新抓取所有 RSS 源
- 短时间内多次运行浪费网络请求
- 调试时反复抓取相同数据

**优化方案**：
```python
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta

class NewsCache:
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def get_rss_cache(self, feed_url: str, max_age_minutes: int = 30) -> Optional[List]:
        """获取 RSS 缓存（30分钟内有效）"""
        cache_key = hashlib.md5(feed_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"rss_{cache_key}.json"

        if cache_file.exists():
            cache_data = json.loads(cache_file.read_text())
            cached_time = datetime.fromisoformat(cache_data['timestamp'])

            if datetime.now() - cached_time < timedelta(minutes=max_age_minutes):
                logger.info(f"Cache hit: {feed_url}")
                return cache_data['items']

        return None

    def set_rss_cache(self, feed_url: str, items: List):
        cache_key = hashlib.md5(feed_url.encode()).hexdigest()
        cache_file = self.cache_dir / f"rss_{cache_key}.json"

        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'items': items
        }
        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False))
```

**实现位置**：
- 新建 `src/news/cache.py`
- 在 `NewsFetcher.fetch_rss_feed` 中集成

**配置项**：
```env
ENABLE_RSS_CACHE=true  # 启用缓存
RSS_CACHE_TTL=30       # 缓存有效期（分钟）
```

**验收标准**：
- [ ] 30 分钟内重复运行使用缓存
- [ ] 超过 30 分钟自动重新抓取
- [ ] 缓存文件保存在 `.cache/` 目录
- [ ] 日志显示缓存命中情况
- [ ] 可通过环境变量禁用缓存

**注意事项**：
- 将 `.cache/` 添加到 `.gitignore`
- 生产环境建议禁用缓存

**预期收益**：
- 本地开发调试时速度提升 10x
- 减少对 RSS 源服务器的压力

---

### 5. 增强 Stage 1 响应解析的健壮性

**影响**：⭐⭐⭐ | **难度**：🔧🔧 | **预计提升**：解析失败率降低 80%

**当前问题**：
- 文件：`src/news/generator.py:170-192`
- 现状：只有一种 JSON 解析方式，LLM 输出格式不符时容易失败
- 影响：解析失败后 fallback 策略过于简单

**优化方案**：

实现三层降级解析策略：

```python
def _parse_selection_response(self, response: str, news_items: dict) -> List[str]:
    """多层降级的 ID 解析"""

    # 层级 1: 标准 JSON 解析
    json_match = re.search(r'\[[\s\S]*?\]', response)
    if json_match:
        try:
            selected_ids = json.loads(json_match.group(0))
            selected_ids = [id for id in selected_ids if id in news_items]
            if 15 <= len(selected_ids) <= 20:
                logger.info("Using JSON parsing")
                return selected_ids
        except json.JSONDecodeError:
            pass

    # 层级 2: 正则表达式提取
    id_pattern = r'(INT-\d+|DOM-\d+)'
    found_ids = re.findall(id_pattern, response)
    valid_ids = [id for id in found_ids if id in news_items]

    # 去重并保持顺序
    seen = set()
    unique_ids = []
    for id in valid_ids:
        if id not in seen:
            seen.add(id)
            unique_ids.append(id)

    if 15 <= len(unique_ids) <= 20:
        logger.info("Using regex extraction")
        return unique_ids

    # 层级 3: 启发式智能选择
    logger.warning("Falling back to heuristic selection")
    return self._heuristic_selection(news_items, target_count=18)

def _heuristic_selection(self, news_items: dict, target_count: int) -> List[str]:
    """基于启发式规则的智能选择"""
    scored_items = []

    for id, item in news_items.items():
        score = 0.0

        # 描述长度（更详细的新闻）
        score += len(item.get('description', '')) * 0.001

        # 关键词匹配
        high_value_keywords = ['breakthrough', 'release', 'launch', 'funding', 'acquisition', 'open-source']
        title_lower = item['title'].lower()
        score += sum(10 for kw in high_value_keywords if kw in title_lower)

        # 来源权重
        premium_sources = ['OpenAI Blog', 'Google AI Blog', 'DeepMind Blog', 'Meta AI Blog']
        if item['source'] in premium_sources:
            score += 20

        scored_items.append((score, id))

    # 按分数排序并选择 top N
    scored_items.sort(reverse=True)
    selected = [id for _, id in scored_items[:target_count]]

    # 确保国际/国内平衡
    int_count = sum(1 for id in selected if id.startswith('INT-'))
    dom_count = sum(1 for id in selected if id.startswith('DOM-'))

    logger.info(f"Heuristic selection: {int_count} international, {dom_count} domestic")
    return selected
```

**验收标准**：
- [ ] JSON 格式正确时优先使用
- [ ] JSON 失败时自动降级到正则提取
- [ ] 正则失败时使用启发式选择
- [ ] 日志记录使用的解析方法
- [ ] 任何情况都能返回 15-20 条新闻

**预期收益**：
- 解析失败率降低 80%
- 降级方案质量接近 LLM 选择
- 更稳定的生产运行

---

### 6. 添加启动配置验证

**影响**：⭐⭐⭐ | **难度**：🔧 | **预计提升**：用户体验显著提升

**当前问题**：
- 文件：`src/config.py`
- 现状：缺少配置必要性检查，运行到一半才发现配置缺失
- 影响：浪费 RSS 抓取时间和 LLM token

**优化方案**：

```python
class Config:
    def __init__(self, config_path: Optional[str] = None):
        load_dotenv()
        self.config_path = self._find_config_file(config_path)
        self.config_data = self._load_yaml_config()

        # 新增：验证配置
        self._validate_config()

        logger.info(f"Configuration loaded from {self.config_path}")

    def _validate_config(self):
        """验证配置完整性"""
        errors = []

        # 1. 检查 LLM 配置
        provider = self.llm_provider
        api_key = self.llm_api_key

        if not api_key:
            errors.append(
                f"Missing API key for provider '{provider}'. "
                f"Set {provider.upper()}_API_KEY in environment."
            )

        # 2. 检查通知配置
        methods = self.notification_methods
        if not methods:
            errors.append(
                "No notification methods configured. "
                "Set NOTIFICATION_METHODS in environment (e.g., 'email,slack')."
            )

        if "email" in methods:
            if not all([os.getenv("GMAIL_ADDRESS"),
                       os.getenv("GMAIL_APP_PASSWORD"),
                       os.getenv("EMAIL_TO")]):
                errors.append(
                    "Email notification enabled but missing credentials. "
                    "Required: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_TO"
                )

        if "slack" in methods and not os.getenv("SLACK_WEBHOOK_URL"):
            errors.append("Slack enabled but SLACK_WEBHOOK_URL not set")

        if "telegram" in methods:
            if not all([os.getenv("TELEGRAM_AI_BOT_TOKEN"), os.getenv("TELEGRAM_AI_CHAT_ID")]):
                errors.append("Telegram enabled but missing TELEGRAM_AI_BOT_TOKEN or TELEGRAM_AI_CHAT_ID")

        if "discord" in methods and not os.getenv("DISCORD_WEBHOOK_URL"):
            errors.append("Discord enabled but DISCORD_WEBHOOK_URL not set")

        if "webhook" in methods and not os.getenv("WEBHOOK_URL"):
            errors.append("Webhook enabled but WEBHOOK_URL not set")

        # 3. 检查语言配置
        languages = self.ai_response_languages
        if not languages:
            errors.append("No valid languages configured (AI_RESPONSE_LANGUAGE)")

        # 4. 报告错误
        if errors:
            error_msg = "\n❌ Configuration validation failed:\n\n" + "\n".join(f"  • {e}" for e in errors)
            error_msg += "\n\nPlease fix the configuration and try again.\n"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("✓ Configuration validation passed")
```

**验收标准**：
- [ ] 所有必需配置缺失时无法启动
- [ ] 错误消息清晰，列出所有缺失项
- [ ] 配置完整时正常运行
- [ ] 日志输出验证通过标志

**预期收益**：
- 快速发现配置问题（启动时 vs 运行 30 秒后）
- 节省 RSS 抓取时间和 LLM token
- 新用户配置体验更好

---

## 🟢 低优先级优化（长期改进）

### 7. 实现性能监控和指标收集

**影响**：⭐⭐ | **难度**：🔧🔧 | **类型**：可观测性

**目标**：收集性能指标，发现瓶颈，优化成本

**优化方案**：

```python
class MetricsCollector:
    def __init__(self):
        self.metrics = {
            'rss_sources': [],
            'llm_stage1_time': 0,
            'llm_stage2_time': 0,
            'llm_tokens': {'input': 0, 'output': 0},
            'news_counts': {
                'fetched': 0,
                'deduplicated': 0,
                'selected': 0,
                'final_chars': 0
            },
            'notifications': []
        }

    def record_rss_fetch(self, source: str, duration: float, count: int, success: bool):
        self.metrics['rss_sources'].append({
            'source': source,
            'duration': duration,
            'count': count,
            'success': success
        })

    def record_llm_stage(self, stage: int, duration: float, tokens: dict):
        self.metrics[f'llm_stage{stage}_time'] = duration
        self.metrics['llm_tokens']['input'] += tokens.get('input', 0)
        self.metrics['llm_tokens']['output'] += tokens.get('output', 0)

    def export_metrics(self, output_file: str = ".metrics/run.json"):
        """导出指标到 JSON 文件"""
        output_path = Path(output_file)
        output_path.parent.mkdir(exist_ok=True)

        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_time': sum([
                self.metrics['llm_stage1_time'],
                self.metrics['llm_stage2_time']
            ]),
            'rss_summary': {
                'total_sources': len(self.metrics['rss_sources']),
                'successful': sum(1 for s in self.metrics['rss_sources'] if s['success']),
                'avg_duration': sum(s['duration'] for s in self.metrics['rss_sources']) / len(self.metrics['rss_sources'])
            },
            'llm_summary': {
                'total_tokens': self.metrics['llm_tokens']['input'] + self.metrics['llm_tokens']['output'],
                'estimated_cost': self._estimate_cost()
            },
            'detailed_metrics': self.metrics
        }

        output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        logger.info(f"Metrics exported to {output_file}")
        return summary

    def _estimate_cost(self) -> float:
        """估算 Claude API 成本"""
        input_tokens = self.metrics['llm_tokens']['input']
        output_tokens = self.metrics['llm_tokens']['output']

        # Claude Sonnet 4.5 pricing: $3/MTok input, $15/MTok output
        cost = (input_tokens / 1_000_000 * 3) + (output_tokens / 1_000_000 * 15)
        return round(cost, 4)
```

**集成位置**：
- 新建 `src/metrics.py`
- 在 `main.py` 中初始化并使用
- 各模块添加 `metrics.record_xxx()` 调用

**验收标准**：
- [ ] 每次运行生成 `.metrics/run.json`
- [ ] 包含所有关键性能指标
- [ ] 可以分析多次运行的趋势
- [ ] 不影响主流程性能（<1% 开销）

**预期收益**：
- 数据驱动的优化决策
- 发现性能瓶颈
- 监控 LLM token 成本

---

### 8. 添加新闻质量预评分机制

**影响**：⭐⭐ | **难度**：🔧🔧🔧 | **类型**：质量优化

**目标**：在 Stage 1 之前预筛选，减少低质量新闻的 LLM 分析

**优化方案**：

```python
def _score_news_item(self, item: dict) -> float:
    """
    评估新闻质量（0-1 分）

    评分维度：
    - 关键词权重 (0-0.3)
    - 来源权重 (0-0.3)
    - 内容质量 (0-0.2)
    - 时效性 (0-0.2)
    """
    score = 0.0

    # 1. 关键词权重
    title_lower = item['title'].lower()
    desc_lower = item.get('description', '').lower()

    high_value_keywords = {
        'breakthrough', 'release', 'launch', 'funding', 'acquisition',
        'open-source', 'announce', 'introduce', 'unveil'
    }
    tech_keywords = {
        'gpt', 'claude', 'llm', 'transformer', 'agent', 'multimodal',
        'reasoning', 'benchmark', 'sota', 'api'
    }

    kw_score = 0
    kw_score += sum(0.05 for kw in high_value_keywords if kw in title_lower)
    kw_score += sum(0.03 for kw in tech_keywords if kw in title_lower)
    score += min(kw_score, 0.3)

    # 2. 来源权重
    source_tiers = {
        'tier1': ['OpenAI Blog', 'Google AI Blog', 'DeepMind Blog', 'Meta AI Blog', 'Microsoft AI Blog'],
        'tier2': ['TechCrunch AI', 'VentureBeat AI', 'MIT Technology Review', 'arXiv'],
        'tier3': ['The Verge AI', 'Ars Technica AI', 'Wired AI']
    }

    if item['source'] in source_tiers['tier1']:
        score += 0.3
    elif item['source'] in source_tiers['tier2']:
        score += 0.2
    elif item['source'] in source_tiers['tier3']:
        score += 0.1

    # 3. 内容质量
    desc_len = len(item.get('description', ''))
    if desc_len > 500:
        score += 0.1
    elif desc_len > 300:
        score += 0.05

    # 检查是否包含具体数字/指标
    if re.search(r'\d+%|\d+x|\$\d+[MB]|\d+\s*(billion|million)', desc_lower):
        score += 0.1

    # 4. 时效性（基于发布时间）
    # TODO: 实现时间解析和评分

    return min(score, 1.0)

def _filter_by_quality(self, news_items: List[Dict], min_score: float = 0.3) -> List[Dict]:
    """过滤低质量新闻"""
    scored = []
    for item in news_items:
        score = self._score_news_item(item)
        if score >= min_score:
            scored.append((score, item))

    # 按分数排序
    scored.sort(reverse=True, key=lambda x: x[0])

    # 记录统计
    logger.info(f"Quality filtering: {len(news_items)} → {len(scored)} items (threshold: {min_score})")
    logger.debug(f"Score distribution: {self._score_distribution([s for s, _ in scored])}")

    return [item for _, item in scored]

def _score_distribution(self, scores: List[float]) -> dict:
    """计算分数分布"""
    bins = {'0-0.3': 0, '0.3-0.5': 0, '0.5-0.7': 0, '0.7-1.0': 0}
    for score in scores:
        if score < 0.3:
            bins['0-0.3'] += 1
        elif score < 0.5:
            bins['0.3-0.5'] += 1
        elif score < 0.7:
            bins['0.5-0.7'] += 1
        else:
            bins['0.7-1.0'] += 1
    return bins
```

**使用位置**：
在 `generate_news_digest_from_sources` 中，`_format_news_with_ids` 之前调用

**验收标准**：
- [ ] 高质量新闻（官方博客、重大发布）得分 > 0.7
- [ ] 低质量新闻（传闻、观点）得分 < 0.3
- [ ] 过滤后保留至少 40-50 条供 Stage 1 选择
- [ ] 日志输出分数分布统计

**预期收益**：
- 减少 Stage 1 的 token 消耗 20-30%
- 提高最终摘要的平均质量

---

### 9. 实现增量更新模式

**影响**：⭐⭐ | **难度**：🔧🔧🔧 | **类型**：性能优化（高频场景）

**适用场景**：本地开发、自建定时任务（每小时/每4小时）

**优化方案**：

```python
class IncrementalUpdater:
    def __init__(self, state_file: str = ".last_run"):
        self.state_file = Path(state_file)

    def get_last_run_time(self) -> Optional[datetime]:
        """读取上次运行时间"""
        if not self.state_file.exists():
            return None

        try:
            data = json.loads(self.state_file.read_text())
            return datetime.fromisoformat(data['last_run_time'])
        except Exception as e:
            logger.warning(f"Failed to read last run time: {e}")
            return None

    def save_run_time(self, stats: dict):
        """保存运行时间和统计"""
        data = {
            'last_run_time': datetime.now().isoformat(),
            'items_fetched': stats.get('fetched', 0),
            'items_selected': stats.get('selected', 0)
        }
        self.state_file.write_text(json.dumps(data, indent=2))

def fetch_news_since(
    self,
    since_time: Optional[datetime] = None,
    min_items: int = 10
) -> Dict[str, List[Dict]]:
    """
    增量抓取：只获取指定时间后的新闻

    Args:
        since_time: 起始时间，None 则全量抓取
        min_items: 最小新闻数，不足则回退全量
    """
    if since_time is None:
        logger.info("Incremental mode: disabled, doing full fetch")
        return self.fetch_recent_news()

    logger.info(f"Incremental mode: fetching news since {since_time.isoformat()}")

    all_news = self.fetch_recent_news()

    # 过滤旧新闻
    filtered = {'international': [], 'domestic': []}

    for category in ['international', 'domestic']:
        for item in all_news[category]:
            pub_time = self._parse_pub_time(item.get('published'))
            if pub_time and pub_time > since_time:
                filtered[category].append(item)

    total_items = len(filtered['international']) + len(filtered['domestic'])

    # 新闻不足，回退全量
    if total_items < min_items:
        logger.warning(
            f"Incremental fetch returned only {total_items} items (< {min_items}), "
            f"falling back to full fetch"
        )
        return all_news

    logger.info(f"Incremental fetch: {total_items} new items since last run")
    return filtered

def _parse_pub_time(self, pub_string: str) -> Optional[datetime]:
    """解析各种 RSS 发布时间格式"""
    if not pub_string:
        return None

    # 尝试多种格式
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",  # RSS 2.0
        "%Y-%m-%dT%H:%M:%S%z",        # ISO 8601
        "%Y-%m-%d %H:%M:%S",          # 简单格式
    ]

    for fmt in formats:
        try:
            return datetime.strptime(pub_string, fmt)
        except ValueError:
            continue

    logger.debug(f"Failed to parse time: {pub_string}")
    return None
```

**配置项**：
```env
ENABLE_INCREMENTAL=true  # 启用增量模式
INCREMENTAL_MIN_ITEMS=10 # 最少新闻数阈值
```

**验收标准**：
- [ ] 首次运行或文件缺失时全量抓取
- [ ] 后续运行只处理新新闻
- [ ] 新闻不足时自动回退全量
- [ ] 日志清晰显示增量 vs 全量模式

**预期收益**：
- 高频运行场景节省 70-80% 资源
- 适合构建实时新闻系统

---

### 10. 改进错误恢复和部分失败容忍

**影响**：⭐⭐ | **难度**：🔧🔧 | **类型**：可靠性

**目标**：提高系统鲁棒性，避免单点故障导致完全失败

**优化方案**：

**1. LLM API 重试**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=30),
    retry=retry_if_exception_type((APIConnectionError, APITimeoutError))
)
def generate(self, messages: List[Dict], **kwargs) -> str:
    """带重试的 LLM API 调用"""
    # 现有实现
```

**2. 细化退出码**
```python
# main.py
EXIT_CODE_SUCCESS = 0           # 全部成功
EXIT_CODE_PARTIAL_SUCCESS = 0   # 部分成功（可接受）
EXIT_CODE_PARTIAL_FAILURE = 1   # 部分失败（需关注）
EXIT_CODE_TOTAL_FAILURE = 2     # 完全失败（需告警）

def main():
    # ...

    # 计算成功率
    total_attempts = len(languages) * len(notification_methods)
    success_count = len(overall_results["sent"])
    success_rate = success_count / total_attempts if total_attempts > 0 else 0

    if success_rate == 1.0:
        logger.info("✓ All notifications sent successfully")
        return EXIT_CODE_SUCCESS
    elif success_rate >= 0.7:
        logger.info(f"⚠ Partial success ({success_rate:.0%})")
        return EXIT_CODE_PARTIAL_SUCCESS
    elif success_rate > 0:
        logger.warning(f"⚠ Partial failure ({success_rate:.0%})")
        return EXIT_CODE_PARTIAL_FAILURE
    else:
        logger.error("✗ Total failure - no notifications sent")
        return EXIT_CODE_TOTAL_FAILURE
```

**3. 降级策略**
```python
def generate_news_digest_from_sources(self, ...):
    try:
        # 尝试两阶段生成
        return self._two_stage_generation(...)
    except Exception as e:
        logger.error(f"Two-stage generation failed: {e}")

        # 降级到简化版
        logger.info("Falling back to simplified digest")
        return self._generate_simplified_digest(news_data)

def _generate_simplified_digest(self, news_data: dict) -> str:
    """降级方案：仅标题和链接"""
    digest = "# AI News Digest (Simplified)\n\n"

    for category in ['international', 'domestic']:
        if news_data[category]:
            digest += f"## {category.title()} News\n\n"
            for i, item in enumerate(news_data[category][:20], 1):
                digest += f"{i}. [{item['title']}]({item['link']})\n"
                digest += f"   Source: {item['source']}\n\n"

    return digest
```

**4. 本地文件备份**
```python
def save_digest_to_file(digest: str, language: str):
    """所有通知失败时保存到文件"""
    output_dir = Path(".output")
    output_dir.mkdir(exist_ok=True)

    filename = f"digest_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{language}.md"
    output_file = output_dir / filename

    output_file.write_text(digest, encoding='utf-8')
    logger.info(f"Digest saved to {output_file}")
```

**验收标准**：
- [ ] LLM API 临时错误自动重试
- [ ] Stage 1 失败能降级
- [ ] 所有通知失败时保存到文件
- [ ] 退出码准确反映执行状态
- [ ] GitHub Actions 日志清晰

**预期收益**：
- 减少因单点故障导致的完全失败
- 更好的故障排查
- 降低人工介入需求

---

## 📝 实施建议

### 立即实施（本周）
1. ✅ 实现 RSS 源并发抓取
2. ✅ 添加新闻去重机制
3. ✅ 实现 RSS 请求重试机制

### 近期实施（本月）
4. ⭕ 添加 RSS 抓取缓存机制
5. ⭕ 增强 Stage 1 响应解析
6. ⭕ 添加启动配置验证

### 长期规划（按需）
7. ⏸ 性能监控和指标收集
8. ⏸ 新闻质量预评分
9. ⏸ 增量更新模式
10. ⏸ 错误恢复优化

---

## 🎯 预期整体收益

完成前 6 项优化后：
- ⚡ 性能：总执行时间减少 **60-70%**
- 💰 成本：LLM token 消耗减少 **15-25%**
- 📈 质量：新闻摘要质量提升 **20-30%**
- 🛡️ 可靠性：错误率降低 **80%**
- 👥 体验：用户配置错误提前发现，体验提升

---

**最后更新**：2026-02-11
**负责人**：待分配
**状态**：待开始
