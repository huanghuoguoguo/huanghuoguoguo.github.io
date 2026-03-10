---
layout: post
title: "Effective Java 读书笔记"
date: 2025-1-29
categories: [后端开发, 读书笔记]
tags: [java, 读书笔记]
comments: true
author: huanghuoguoguo
---

很早之前看的这本书，当时觉得条条有理，但合上书该怎么写还是怎么写。后来在项目里被包装类型的 GC 风暴教训过一次（见 [int[] 遍历比 Integer[] 快近 5 倍：从内存布局到 CPU Cache 的实证](/posts/Java基本类型vs包装类型/)），回头翻书才发现——条目 6"避免创建不必要的对象"、条目 61"基本类型优于装箱类型"，白纸黑字写在那里，之前就是没感觉。

或许不是因为没读进去，而是还没有被足够多的 bug 教训过。等教训攒够了，这些条目自然会变成条件反射。

这篇笔记不打算逐章摘要——12 章 90 条，每条一句话和翻目录没区别。只挑四个我真正有感触的主题展开，其余章节用一张表一笔带过。

<!-- more -->

---

## 第 2 章 创建和销毁对象（条目 1-9）

核心目标：让对象"生得优雅、死得干净"，把内存泄漏、资源泄漏、构造失败这三颗雷一次性拆光。

| 做法 | 为什么 | 不做会怎样 |
|------|--------|-----------|
| 静态工厂 `Boolean.valueOf()` | 有名字、可缓存（享元）、可返回子类型 | `new Boolean(true)` 每次堆上新建，内存浪费；构造器无法描述语义 |
| 构建器（Builder） | 参数 >4 个时，逐字段 set 会漏必填项；Builder 编译期就能拦住漏填 | 无参构造 + setter 出现"半初始化"对象，多线程下 NPE |
| 对象池（仅重量级资源） | 线程、连接、DirectByteBuffer 的创建成本远高于内存成本 | 每次 `new Thread` 或 `new Socket`，QPS 一高 CPU 花在内核调度 |
| try-with-resources | 保证任何退出路径都自动 `.close()`，保持异常原始栈 | finally 里也抛异常时第一个异常被吞；高并发下文件句柄耗尽 |

### 静态工厂 vs 构造器：一个例子

```java
// 构造器：没有语义，看不出在干什么
new BigInteger(String, int)

// 静态工厂：有名字，意图清晰
BigInteger.probablePrime(int, Random)
```

静态工厂的隐藏好处：可以返回缓存的实例。`Boolean.valueOf(true)` 永远返回同一个对象，而 `new Boolean(true)` 每次在堆上分配。这和条目 6"避免创建不必要的对象"直接相关——在 [包装类型的性能实测](/posts/Java基本类型vs包装类型/) 里可以看到，一个 `Integer` 对象 16 字节（对象头 12B + value 4B），400 万个 `Integer` 比 400 万个 `int` 多吃 63MB 内存，遍历慢近 5 倍。**对象创建不是免费的，在热路径上必须精打细算。**

### Builder 模式的"半初始化"陷阱

```java
// 无参构造 + setter：对象在 set 完之前处于不一致状态
NutritionFacts cocaCola = new NutritionFacts();
cocaCola.setServingSize(240);
cocaCola.setServings(8);
// 如果这里另一个线程读了 cocaCola，calories 还是 0
cocaCola.setCalories(100);

// Builder：对象要么完整，要么不存在
NutritionFacts cocaCola = new NutritionFacts.Builder(240, 8)
    .calories(100)
    .sodium(35)
    .build(); // build() 里做参数校验，不合法就抛异常
```

Builder 还有一个好处：`build()` 返回的对象可以是不可变的。不可变对象天生线程安全，不需要同步——这和第 4 章"最小可变性"以及第 11 章的并发安全直接衔接。

---

## 第 4 章 类和接口（条目 15-25）

最小可变性、接口优于抽象类、组合优于继承——设计"可扩展又不可滥用"的 API。

读这章的时候自然会想到一个问题：这些原则在其他语言里是怎么落地的？Java 靠的是程序员自觉遵守，有些语言直接在语言层面强制了。

### 三种语言的对比

| 维度 | Java | Go | Rust |
|------|------|----|------|
| 最小可变性 | `final` 字段 + 构造器保证发布后只读 | 值类型按值返回实现快照式不可变 | 所有权系统编译期保证 `&T` vs `&mut T` |
| 接口 vs 抽象类 | 单继承，接口 + default 方法 | 只有 interface，隐式实现 | trait，可带默认实现，支持静态/动态派发 |
| 组合 vs 继承 | 委托/代理模式复用行为 | 嵌入（embedding）是"字段提升"语法糖 | 字段/泛型包裹，`#[derive]` 自动实现 |

三者都把"组合优于继承"写进了语言设计，只是约束力度 Rust > Go > Java。Java 给你 `extends` 然后告诉你别用，Go 直接不给你继承，Rust 更进一步——连可变性都编译期管死。

> 更详细的跨语言并发模型对比，见 [并发模型与语言选型：从 Java 出发看各语言的并发哲学](/posts/并发模型与语言选型/)。

Rust 的**零成本抽象**值得单独提一嘴：泛型单态化生成专用代码，迭代器链编译后展开成单循环，所有权/借用检查只在编译期——"写起来像高层语言，运行起来像手写汇编"。这和 Effective Java 追求的目标其实一样：用好语言特性减少运行时开销。只是 Java 受限于泛型擦除和对象模型，很多时候需要靠工程手段弥补（比如用 Eclipse Collections 的 `IntArrayList` 绕过 `List<int>` 不存在的问题）。

### 组合优于继承：为什么

```java
// 继承：HashSet 的 addAll() 内部会调 add()，重写 add() 时计数会重复
public class InstrumentedHashSet<E> extends HashSet<E> {
    private int addCount = 0;

    @Override public boolean add(E e) {
        addCount++;
        return super.add(e);
    }

    @Override public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c); // 内部调 add()，addCount 被加了两次！
    }
}

// 组合：不依赖父类实现细节，行为完全可预测
public class InstrumentedSet<E> extends ForwardingSet<E> {
    private int addCount = 0;

    @Override public boolean add(E e) {
        addCount++;
        return super.add(e); // 委托给内部 Set，不怕实现变动
    }

    @Override public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c); // ForwardingSet.addAll() 逐个调自己的 add()
    }
}
```

继承的问题不是"功能不够"，而是子类和父类的实现细节耦合太深。父类的 `addAll()` 内部调不调 `add()`，是实现细节，不是契约——一旦父类改了实现，子类就炸。组合把这层耦合切断了。

---

## 第 9 章（条目 61）× 第 2 章（条目 6）：基本类型优于装箱类型

这一条单独拎出来，是因为我在项目里真的被它教训过。

条目 61 说：**基本类型优于装箱类型**。条目 6 说：**避免创建不必要的对象**。两条加在一起的意思就是——在性能敏感的代码里，`Double` 和 `double` 不是一回事。

```java
// 反例：自动装箱的隐形代价
Long sum = 0L;
for (long i = 0; i < Integer.MAX_VALUE; i++) {
    sum += i; // 每次 += 都触发自动拆箱和装箱，创建约 2^31 个 Long 对象
}
```

这段代码功能上没问题，但 `Long sum` 改成 `long sum`，性能差距是数量级的。

更深入的分析见 [int[] 遍历比 Integer[] 快近 5 倍：从内存布局到 CPU Cache 的实证](/posts/Java基本类型vs包装类型/)，那篇文章用 benchmark 和 `perf stat` 实测了包装类型的真实代价：

- **内存膨胀 5 倍**：`int` 4 字节，`Integer` 对象 16 字节 + 引用 4 字节 ≈ 20 字节
- **顺序遍历慢 4.8 倍**：`Integer[]` 破坏空间局部性，CPU prefetcher 失效，L1/L2 cache miss 频发
- **指针追逐**：`int[]` 连续平铺像 C 数组，`Integer[]` 是指针数组 + 散落的堆对象，每次访问多一跳

在那个存储性能指标采集系统里，把 `MetricsSnapshot` 的指标字段从 `Double`/`Long` 改成 `double`/`long`，配合对象缓存复用，单周期延迟从 100ms 降到 60ms。**Effective Java 条目 6 和 61 不是面试八股，是真能省钱的。**

---

## 第 11 章 并发（条目 78-84）

同步访问共享可变数据、避免过度同步、Executor 优于 Thread、并发工具优于 wait/notify——这些条目在 [《Java 并发编程的艺术》读书笔记](/posts/java并发编程的艺术/) 里有更底层的展开，这里只聊几个和 Effective Java 特别相关的点。

### 条目 78：同步访问共享可变数据

```java
// 反例：没有同步，另一个线程可能永远看不到 stopRequested 变为 true
private static boolean stopRequested;

// 修复方案一：volatile（保证可见性）
private static volatile boolean stopRequested;

// 修复方案二：AtomicBoolean（可见性 + 原子性）
private static final AtomicBoolean stopRequested = new AtomicBoolean(false);
```

`volatile` 保证可见性但不保证原子性。如果只是一个 boolean 标志位，`volatile` 够用；如果是 `count++` 这种复合操作，必须用 `AtomicLong` 或加锁。

这背后的原理是 JMM（Java Memory Model）的 happens-before 关系——在 [并发编程的艺术](/posts/java并发编程的艺术/) 里从 CPU 缓存一致性协议和内存屏障的角度有更详细的拆解。Effective Java 告诉你"要同步"，《并发编程的艺术》告诉你"为什么不同步就会出问题"。

### 条目 80：Executor 优于 Thread

```java
// 反例：每个任务一个线程，QPS 高时线程爆炸
new Thread(task).start();

// 正确做法：线程池复用
ExecutorService exec = Executors.newFixedThreadPool(nThreads);
exec.submit(task);
```

但 `Executors.newFixedThreadPool` 和 `newCachedThreadPool` 各有陷阱——前者队列无界可能 OOM，后者线程数无上限可能耗尽系统资源。生产环境应该用 `ThreadPoolExecutor` 显式指定核心参数。

在前面提到的指标采集系统里，最终用的是 `CompletableFuture` + 自定义线程池做分片并行计算，配合 `StampedLock` 做读多写少场景的锁优化。这些都是 Effective Java 第 11 章条目的直接应用。

---

## 其余章节速览

以下章节没有深入展开，用一张表留个索引，踩坑时回来查。

| 章节 | 主题 | 核心要点 |
|------|------|---------|
| 第 3 章（条目 10-14） | 通用方法 | `equals` 和 `hashCode` 必须一致，违反会导致 HashMap/HashSet 行为不可预期 |
| 第 5 章（条目 26-33） | 泛型 | 消除 raw type、PECS 原则（Producer-Extends, Consumer-Super）、异构容器 |
| 第 6 章（条目 34-41） | 枚举和注解 | 用 enum 代替 int 常量、EnumSet/EnumMap 代替位运算 |
| 第 7 章（条目 42-48） | Lambda 和 Stream | 方法引用优于 lambda、Stream 无副作用、慎用并行流 |
| 第 8 章（条目 49-56） | 方法设计 | 参数校验、防御性拷贝、慎用重载与可变参数、Optional 返回 |
| 第 10 章（条目 69-77） | 异常 | 异常只用于异常情况、受检/运行时异常分层、失败原子性 |
| 第 12 章（条目 85-90） | 序列化 | Java 原生序列化是历史包袱，用 JSON/ProtoBuf 替代 |

---

## 这些方法，有什么观测手段？

书里讲了 90 条"应该怎么写"，但光靠自觉和记忆是不可能全部遵守的。真正让这些实践落地，需要的是**可观测性**——能在代码写出来之后、甚至写的过程中，自动检测到违反了哪些条目。

### 静态分析：编译期和提交前拦截

最直接的观测手段是静态分析工具，它们能在代码还没运行的时候就抓出问题：

| 工具 | 能抓到什么 |
|------|-----------|
| Error Prone（Google） | raw type 使用、`equals` 不一致、资源未关闭、不安全的序列化 |
| SpotBugs | 空指针风险、并发问题、性能反模式（如在循环中拼字符串） |
| SonarQube | 代码异味、圈复杂度、重复代码、安全漏洞 |
| Checkstyle / PMD | 命名约定、代码风格、未使用的导入 |
| IntelliJ IDEA Inspections | 覆盖面最广，几乎每一条 Effective Java 都有对应的检查项 |

这些工具应该接入 CI 流水线——在标准的部署流水线架构里，静态分析属于提交阶段，和编译、单元测试一起跑。如有报错坚决不让合入主干。

### 运行时观测：JVM 监控和性能工具

有些问题静态分析抓不到，必须在运行时才能看见：

| 关注点 | 观测手段 | 对应的条目 |
|--------|---------|-----------|
| 对象创建过多 | GC 日志、`jstat -gc`、JFR 的对象分配火焰图 | 条目 1（静态工厂）、条目 6（避免不必要的对象） |
| 资源泄漏 | `-XX:+HeapDumpOnOutOfMemoryError` + MAT 分析、文件句柄监控 | 条目 8（try-with-resources）、条目 9（终结器） |
| 并发问题 | `jstack` 线程快照、死锁检测、JFR 的锁竞争事件 | 条目 78-84（并发章节） |
| 序列化安全 | 依赖扫描（CVE 数据库）、反序列化攻击检测 | 条目 85-90（序列化章节） |

像 jps/jstat/jmap/jstack/JFR 这套基础的 JVM 诊断工具链，和 Effective Java 的并发、对象创建章节是直接对应的。在 [包装类型性能实测](/posts/Java基本类型vs包装类型/) 那篇文章里，就是用 MAT 分析堆内存才定位到 `java.lang.Double` 是分配大户的。

### 测试：契约验证

有些条目的正确性只能通过测试来保证：

- **equals/hashCode 一致性**：写测试验证 `a.equals(b)` 时 `a.hashCode() == b.hashCode()`
- **Comparable 自反性/传递性**：随机生成对象对，验证排序结果稳定
- **不可变类的线程安全**：多线程并发读写测试，验证不可变对象确实不可变
- **Builder 的必填字段**：编译期拦截最好，否则用测试验证缺少必填字段时抛出合适异常

这和《测试驱动开发》的思路一致：先写测试定义"对的行为"，再写代码实现。对于 equals/hashCode 这种容易写错的契约，测试比 Code Review 可靠得多。

### 代码审查：人的判断

工具能覆盖规则性的检查，但有些条目需要人的判断：

- 条目 18"组合优于继承"——工具不知道你的继承关系是否合理
- 条目 15"最小化可访问性"——哪些类应该是包私有的，取决于设计意图
- 条目 49"参数校验"——校验逻辑是否覆盖了所有边界条件

这些属于 Code Review 清单的范畴，最终还是回到团队纪律上。

### 小结

把观测手段按反馈速度排序：

```
IDE 实时检查 → 编译期静态分析 → 单元测试 → CI 流水线 → Code Review → 运行时监控 → 线上事故
```

越靠前发现问题，修复成本越低。Effective Java 的 90 条建议，大部分都可以在前四个阶段被自动化地观测到。剩下的靠人的判断和经验——而经验，就是踩过坑之后回头翻书时那种"原来如此"的感觉。
