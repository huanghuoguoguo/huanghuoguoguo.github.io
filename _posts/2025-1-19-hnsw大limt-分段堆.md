---
layout: post
title: "HNSW 索引优化：基于分段堆应对大 LIMIT 查询"
date: 2025-01-19
categories: [数据库, 核心算法]
tags: [向量索引, hnsw, 性能调优, C++]
comments: true
author: huanghuoguoguo
---

HNSW（Hierarchical Navigable Small World graphs，分层可导航小世界图）可以说是目前工业界影响力最大、应用最广的基于图的近似最近邻搜索（ANN）算法。它以极快的搜索速度和出色的召回率著称。
然而，尽管 HNSW 享有盛名，要在一个工业级数据库引擎中将其性能压榨到极致却并不容易。

本文主要探讨在参与 OceanBase 数据库大赛（标量与向量混合查询赛道）期间，针对 **大 LIMIT 场景** 下所做的一项关于 **分段堆（Segmented Heap）** 的优化探索。

---

## 一、破局点：大 LIMIT 查询带来的性能瓶颈

在 OB 国赛的测试场景中，经常面临大 limit 的标量-向量混合查询。例如以下 SQL：

```sql
-- 基础基于 ANN Benchmarks 的查询
SELECT id
FROM items1
ORDER BY L2_distance(embedding, vector) approximate 
LIMIT 10000;

-- 带有标量过滤的混合检索场景
SELECT id
FROM items1
WHERE c1 = 123
ORDER BY L2_distance(embedding, vector) approximate 
LIMIT 10000;
```

赛题底层框架（VSAG 的 HNSW 实现，实际上参考了著名的开源在 `nmslib/hnsw` 库的实现机制）在处理此类 Top-K 时，**全局只维护一个大顶堆**来存储候选点集。

**问题出在哪里？**
当 `LIMIT` 数据量极大（比如 10000）时，堆的大小随之膨胀。每次将一个新近邻候选点换入大堆并调整结构时，极其容易因为随机的内存访问而**无法有效利用 CPU 的 L1/L2 高速缓存（Cache Miss）**。
- **全局堆的调整**：入堆/出堆操作大概需要 `2 * log(10000) ≈ 27` 次比较。
- **分段堆的设想**：将这 10000 个元素拆分成 100 个容量为 100 的小堆。每次调整的比较次数大概是 `4 * log(100) ≈ 26` 次。

虽然在算法时间复杂度（大 O 表示法）上两者几乎相同，但**分段堆由于每次调整时内存下标高度集中，具有极佳的缓存局部性**，能大幅度降低由于访问跨度过大带来的 CPU 缓存失效惩罚。的思路。

---

## 二、分段堆的设计与原理解析

为了打破缓存访问的瓶颈，我们引入了“分段堆”来分割候选集合。

![HNSW 分段堆设计结构](/images/hnsw.png)

### 1. 分块策略
全局不再维护单一的庞然大堆，而是将候选点分成多个**块（Block）**，每个块的大小设为 `ef`（搜索范围参数）。如果总查询量是 `k`，块的数量即为 `k / ef`。

### 2. 堆的分级管理机制
- **局部小堆构建**：当候选点数量达到 `k` 时，不再对这 `k` 个点整体建堆，而是对每个块分别构建最小堆，并独立记录每个堆的**最大值**。
- **全局 Key 堆维护**：我们额外维护一个全局的最小堆（我们称之为 `key 堆`），用于存储在第一步中提取出来的**每个块的最大向量距离，以及它所对应的块起始地址**。
- **定位与裁决**：依靠全局的 `key 堆`，我们可以用极小的代价，快速锁定当前所有小堆中“最大”（距离最远）的那一个元素，从而确立整个结果集的全局门槛（下界 `lowerBound`）。

### 3. 延迟建堆与预取优化（Prefetch）
进一步的优化手段包括：
- **延迟/异步建堆**：当检索结果节点还未装满 `k` 时，完全可以跳过建堆成本，直接 `vector.push_back` 将其存入数组。只有当数据量饱和、需要进行“末尾淘汰”时，才进行结构化的调整。
- **SSE 指令预取**：我们在遍历图节点的关联点之前，使用 CPU 底层汇编预取指令 `_mm_prefetch` 提前去内存里把可能要访问到的向量数据捞进缓存，隐藏 DRAM 的高延迟。

---

## 三、C++ 核心实现片段

下面是分段堆在 HNSW 算法中搜索基础层的核心逻辑修改 (`searchBaseLayerSTLarge`)：

```cpp
template <bool has_deletions, bool collect_metrics = false>
std::vector<std::pair<float, int64_t>>
searchBaseLayerSTLarge(tableint ep_id, const void* data_point, size_t k, size_t ef, BaseFilterFunctor* isIdAllowed = nullptr) const {
    auto vl = visited_list_pool_->getFreeVisitedList();
    vl_type* visited_array = vl->mass;
    vl_type visited_array_tag = vl->curV;
    auto comp = CompareByFirst();
    
    // 声明每个块大小及区间数
    const size_t block_size = ef;
    const size_t block_nums = k / ef;
    
    // 存储候选值的数组，分成 block_nums 个块，每个块是一个堆
    alignas(64) std::vector<std::pair<float, int64_t>> vectors;
    vectors.reserve(k);

    // 存储每个块的最大值及其在 vectors 数组中的起始索引
    alignas(64) std::vector<std::pair<float, int64_t>> key;
    key.reserve(block_nums);

    std::priority_queue<std::pair<float, int64_t>, vsag::Vector<std::pair<float, int64_t>>, CompareByFirst> candidate_set(allocator_);

    float lowerBound;
    float dist = fstdistfunc_(data_point, getDataByInternalId(ep_id), dist_func_param_);
    lowerBound = dist;

    // 初始点加入
    vectors.emplace_back(dist, ep_id);
    visited_array[ep_id] = visited_array_tag;
    candidate_set.emplace(-dist, ep_id);

    while (!candidate_set.empty()) {
        std::pair<float, tableint> current_node_pair = candidate_set.top();

        if ((-current_node_pair.first) > lowerBound && vectors.size() >= k) {
            break;
        }
        candidate_set.pop();

        tableint current_node_id = current_node_pair.second;
        int* data_ptr = (int*)get_linklist0(current_node_id);
        size_t size = getListCount((linklistsizeint*)data_ptr);

        // 使用系统底层指令预取优化
        auto vector_data_ptr = data_level0_memory_->GetElementPtr((*(data_ptr + 1)), offsetData_);
#ifdef USE_SSE
        _mm_prefetch((char*)(visited_array + *(data_ptr + 1)), _MM_HINT_T0);
        _mm_prefetch((char*)(visited_array + *(data_ptr + 1) + 64), _MM_HINT_T0);
        _mm_prefetch(vector_data_ptr, _MM_HINT_T0);
        _mm_prefetch((char*)(data_ptr + 2), _MM_HINT_T0);
#endif

        for (size_t j = 1; j <= size; j++) {
            tableint candidate_id = *(data_ptr + j);
            size_t pre_l = std::min(j, size - 2);
            auto vector_data_ptr = data_level0_memory_->GetElementPtr((*(data_ptr + pre_l + 1)), offsetData_);
#ifdef USE_SSE
            _mm_prefetch((char*)(visited_array + *(data_ptr + pre_l + 1)), _MM_HINT_T0);
            _mm_prefetch(vector_data_ptr, _MM_HINT_T0);
#endif
            // 若节点未访问
            if (visited_array[candidate_id] != visited_array_tag) {
                visited_array[candidate_id] = visited_array_tag;
                float dist = fstdistfunc_(data_point, getDataByInternalId(candidate_id), dist_func_param_);

                if (vectors.size() < k) {
                    // 数据池未满，直接存入
                    vectors.emplace_back(dist, candidate_id);
                    candidate_set.emplace(-dist, candidate_id);
                    
                    if (vectors.size() == k) {
                        // 当数据池首次达到k大小时，批量建立分块堆结构
                        for (size_t i = 0; i < block_nums; i++) {
                            size_t start = i * block_size;
                            size_t end = (i + 1) * block_size;
                            std::make_heap(vectors.begin() + start, vectors.begin() + end, comp);

                            // 记录每个块的最大值到 key 集合中
                            float max_value = (vectors.begin() + start)->first;
                            key.emplace_back(max_value, start);
                        }
                        // 建立 key 的最小/最大汇聚堆
                        std::make_heap(key.begin(), key.end(), comp);
                        lowerBound = key.front().first;
                    }
                } else if (dist < lowerBound) {
                    // 当新元素的距离小于最劣解，需要执行挤出动作
                    candidate_set.emplace(-dist, candidate_id);
                    
                    // 从全局 key 管理表中弹出劣解所在的区块标识
                    std::pop_heap(key.begin(), key.end());
                    size_t block_start = key.back().second;

                    // 定位并更新对应具体区块的最大值
                    auto block_begin = vectors.begin() + block_start;
                    auto block_end = block_begin + block_size;
#ifdef USE_SSE
                    _mm_prefetch(reinterpret_cast<const char*>(&vectors[block_start]), _MM_HINT_T0);
#endif
                    std::pop_heap(block_begin, block_end, comp);
                    *(block_end - 1) = std::make_pair(dist, candidate_id); // 覆盖写入新值
                    std::push_heap(block_begin, block_end, comp);

                    // 同步更新全局 Key 池的登记信息
                    key.back() = std::make_pair(block_begin->first, block_start);
                    std::push_heap(key.begin(), key.end(), comp);
                    
                    // 收回游标基准线
                    lowerBound = key.front().first;
                }
            }
        }
    }
    visited_list_pool_->releaseVisitedList(vl);
    return std::move(vectors);
}
```

---

## 四、实战复盘与性能反思

虽然通过拆解大堆并在理论上极具针对性地优化了 L1/L2 缓存访问，但通过严格的压测对标，这一改动**实际只带来了大概 5% 的微弱性能涨幅。** 

问题究竟出在哪？排查后我们得出以下几点反思：

1. **缓存行局限性（Cache Line Trap）**：通常现代 CPU 的 Cache line 也就是 64 字节。即使我们引入了分段堆机制，一个 100 元素的段如果由粗粒度对象的 vector 组成，其总体积很可能轻易就撑破或部分跨越了同一个可用的缓存层级，依然难以避开强制未命中的魔咒。
2. **多线程并发开销（Thread-Sync Cost）**：如果打算利用 OpenMP 之类的东西为底层不同块的建推提供并行计算能力，在单条查询耗时本身只在毫秒级时，线程上下文切换的唤醒成本（比如 OpenMP 的 `parallel for` 带来的极高隐式屏障同步）很可能会反噬提速效果。
3. **向量原始数据不连续**：大 LIMIT 时我们虽然优化了排序所用的 Heap Index 的局部性，但是每一次“比较”都伴随这去真实图节点中拿 `embedding vector`；如果图中原始数据节点本身存储支离破碎，这里产生的缓存断层远超堆比较所带来的损失。

### 思考与后续推进方向
针对纯结构类的大 LIMIT 瓶颈已摸到天花板情况：
- **混合使用 SQ4 等降维压缩（Quantization）技术**直接压榨底层数据结构所占用的吞吐。
- 转而利用更低层级如 `AVX-512` 等 SIMD 数据并行指令来提纯“比较本身”的速度。
- 继续改造内存分配器，把图节点内存和它的指针数组做成物理连续强相关的内存区以大幅度解决散乱问题。

一次微小的 5% 的优化，背后折射的恰恰是：**工程不仅需要精妙的算法思想，更需要能够洞穿内存物理特性的硬件级思维。**