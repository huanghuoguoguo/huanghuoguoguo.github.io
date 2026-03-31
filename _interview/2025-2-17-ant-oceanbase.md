---
layout: post
title: "蚂蚁 OceanBase 一面（测开）——表述混乱的代价"
date: 2025-2-17
comments: true
author: huanghuoguoguo
tags: ["蚂蚁集团", "OceanBase", "测开", "一面"]
---

研二找暑期实习的一场面试，蚂蚁集团 OceanBase 团队，**测试开发岗位**。面试官是 backend infra 方向的。

面试中暴露出的核心问题：**表述没有经过充分思考，回答太快导致漏掉信息；没有引导或引导过少时，回答得牛头不对马嘴；不能理解面试官想问的问题方向。**

<!-- more -->

---

## 自我介绍

两分钟自我介绍，**没有讲得很流畅，卡壳了**。提到实习和比赛有很多收获，后续提问由这个开场。

**实习时长**：说的六个月。

---

## OB 大赛和中科曙光实习的收获

**Q: 在 OB 大赛、中科曙光实习中收获最大的是什么？**

这个问题值得好好总结，但当时答得流水账。现在整理：

### OB 初赛

接触到了怎么实现一个存储引擎。包括：

- 语法和词法分析
- 优化器、执行器
- 存储引擎代码编写

MiniOB 实现了可用的存储机制，包括 Disk Buffer Pool、Record Manager、MVCC 等，让我对存储机制了解得更深入。

### OB 国赛

对性能优化有了一个具体的认知。第一次对如此细粒度的性能优化有了清晰的概念：

- 缓存预取
- 指令流水线冲突
- Cache Line 带来的提升

通过火焰图和提测结果直观感受到性能的提升。

### 中科曙光实习

- 学习到了很多存储知识
- 公司框架：Job 框架、EventBus 框架、告警框架、性能指标框架
- 团队合作开发、需求分析讨论、Git 协作

这些经历为我之后参加比赛、自己实现框架都很有益处。

> **反思**：当时答得太流水账，没有重点。应该先说结论——"OB 比赛让我从 0 到 1 实现了存储引擎，对内核有了直观认知；曙光实习让我接触到企业级开发流程和框架设计"，再展开细节。

---

## 遇到的困难

### 最大的困难是什么？

**在 MiniOB 中实现向量索引并通过 Benchmark 赛题。**

因为 Benchmark 有硬性要求，不像其他赛题通过部分样例就行——需要 90% 召回率和 1.5G 内存限制。

一开始决定自己实现向量索引时：

1. 尝试自己编写分类代码（IVF，类似 K-Means），效果不理想
   - 建立索引时间非常长
   - 只有 30 的 QPS 和 30 的召回率
   - 离 100 QPS 和 90% 召回率差得远
   - 尝试了两天，一度想放弃

2. 引入别人的开源 HNSW 实现
   - 维度较高，直接存储内存爆了
   - 当时没有量化和维度压缩的概念

3. 从头到尾捋调用链
   - 发现插入之后还未建立索引时有很大一部分内存占用
   - 找到 YACC 读取向量时的内存泄漏
   - 优化字符串转向量的效率

4. 最后实现 IVF-HNSW 索引，勉强达到要求

### 国赛阶段的困难

- **环境部署和编译**：花了非常长时间搭建环境，解决编译不生效问题
- **资源限制**：没想到 OB 对资源要求那么高，磁盘和内存频繁爆满，多次重新搭建环境
- **代码量巨大**：完全不知道从哪里入手，听培训后找到关键代码做改动

影响比较大的技术难点：

- 找不到如何将算子下推、如何将辅助表切断，重心主要落在 HNSW 内存索引优化上（事实证明有必要切断辅助表）
- 尝试 IVF-HNSW 效果不理想
- 尝试动态搜索参数，效果不理想
- 最终有了一些起色，但还是没进前 20

### 中科曙光实习的困难

- **复杂的业务和自研框架**：一开始没人带，导师在忙新需求（用 Go 适配 K8s）
- **独自摸索**：帮组里补单元测试，看调用逻辑，理解业务实现
- **沟通协调**：和组内人员沟通、软硬件联调、和其他组交涉、负责进度

---

## 中科曙光的 Java 定位

**Q: 在中科曙光的实习中，Java 是作为管理层面的软件还是 IO 层面？**

答：管理层面。主要职责是接收用户指令，对指令进行分发和管理。使用 Raft 分布式一致性缓存层实现元数据管理，对各种 Job 实现互斥、优先级、重试管理。

IO 则是 C++ 做的。

---

## 对 IO 的理解

**Q: 对 IO 的理解？**

这里走到坑里了——光顾着考虑数据传输的 IO，忘记 Socket 的 IO，还有 Java 字符/字节流的 IO。

当时回答了：

### 缓冲区 IO

需要和磁盘频繁交互的地方一般都会有缓冲区：

- Innodb 中的 Disk Buffer Pool、Double Write Buffer Pool、Redo Log（环形缓冲区）
- Linux 的 Page Cache（要用 `fsync` 刷入磁盘）
- Redis 的 AOF（会主动调用 `fsync` 刷入磁盘）

### 顺序追加比随机读写快

- Kafka 高性能：mmap 和 sendfile，减少上下文切换和拷贝次数，页面预取
- LSM 树：OceanBase 和 Kafka 用它做存储结构，MemTable 是 B+ 树和 Hashtable，读写非常快
- IO 协议：SCSI、TGT 等（没想起来）

### 漏掉的 Socket IO

因为前一个问题问我曙光项目的 IO 是不是用 Java 做的，所以完全只想到了存储层面的 IO，没想到网络层面：

- IO 多路复用
- BIO、NIO
- epoll、poll、select
  - Redis 在网络 IO 层面使用了 IO 多路复用（epoll）
  - Tomcat 高版本也使用了 IO 多路复用
  - Netty 以 NIO 和 IO 多路复用出名

---

## 存储协议

**Q: 中科曙光的底层协议是块存储吗？**

答得流水账，其实不是很清楚是流存储还是块存储。面试官肯定了是块存储。

LUN 是块存储中的概念，所以是块存储。与之同级的还有文件存储、对象存储。

块存储性能最高，用 SCSI、FC 协议进行 IO 传输。

---

## 数据库

**Q: 数据库系统学过吗？**

答：学过。（但没说清楚是名词还是动词）

**Q: SQL 题：学生表查第三名总成绩的各科成绩**

要用窗口函数：

```sql
WITH RankedStudents AS (
    SELECT
        student_id,
        name,
        class_id,
        math,
        chinese,
        english,
        (math + chinese + english) AS total_score,
        ROW_NUMBER() OVER (PARTITION BY class_id ORDER BY (math + chinese + english) DESC) AS rank
    FROM students
)
SELECT
    student_id,
    name,
    class_id,
    math,
    chinese,
    english,
    total_score
FROM RankedStudents
WHERE rank = 3;
```

**Q: SQL 语句的执行顺序**

答：FROM、JOIN、WHERE、GROUP BY、ORDER BY、LIMIT。

在初赛完成 MiniOB 的过程中需要完成这部分工作，对算子连接有印象。

具体顺序应该是：JOIN、WHERE、GROUP BY、ORDER BY、LIMIT、PROJECT。

---

## MySQL 对比

**Q: MySQL 数据库有没有对比使用过？**

没听到"对比"二字。

应该回答用过哪些数据库，以及它们之间的不同特性：

- **OceanBase vs MySQL**：
  - OB 原生分布式、原生分区
  - MySQL 实现分库分表分区比较麻烦，官方提供的不太好，或用第三方如 ShardingSphere
  - OB 支持自动分区

- **NoSQL**：
  - OB 说自己是 NewSQL（多模态）
  - ES、MongoDB、Redis、Kafka

---

## 代码阅读

**Q: 是否看过具体代码（MySQL）？**

答：初赛时完善和看过了 MiniOB 大部分代码，对整体结构、语法和词法分析、存储引擎、优化器等都有所了解。

---

## Java 基础

**Q: 继承、反射、多态**

只说"用过"，没有具体讲概念。应该补充：

### 继承

一个类（子类）继承另一个类（父类）的属性和方法。作用：
- 代码复用
- 层次化建模
- 实现多态（基础）

### 反射

让 Java 有了运行时按需加载字节码和修改字节码的能力。作用：
- 动态编程
- 框架开发（Spring、Hibernate 依赖注入、ORM）
- 调试和测试

### 多态

同一种行为在不同对象上有不同实现。作用：
- 灵活性
- 可扩展性
- 代码复用

---

## 多线程并发

**Q: 多线程并发有没有在开发中使用过？**

答：性能指标场景。

其实还可以说 Job 框架——内部有大量并发任务调度。

---

## Linux

**Q: 处理字符串的脚本**

答：替换用 `sed`。

```bash
sed 's/old/new/g' filename
```

进阶用法：
- 直接编辑文件：`sed -i 's/old/new/g' filename`
- 删除空白行：`sed '/^$/d' filename`
- 提取特定范围：`sed -n '2,5p' filename`

**Q: 查看 CPU、IO、内存压力的脚本**

答：用 `top` 或 `htop`，没有持续监控并转储过。

应该写一个完整的监控脚本，包括：
- 每 5 秒采集 CPU 使用率（`top` 解析）
- 内存使用率（`free` 解析）
- IO 压力（`vmstat` 解析）
- Top 10 进程（`ps aux` 排序）
- 按天存储日志

---

## Python 熟悉程度

**Q: 对 Python 熟悉多少？**

答：写过一些脚本。

---

## 手写代码

### 最小窗口子串

返回包含目标字符的最小窗口。`str = "this is a text"`, `tgt = "txt"`，输出 `"text"`。

写了滑动窗口解法，但面试官的代码有卫语句（判空提前返回），更简洁。

### 奇偶消费线程

多线程交替打印奇偶数。

写了 `wait/notify` 版本，但面试官给了 `ReentrantLock + Condition` 的更优雅实现：

```java
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

class OddEvenPrinter {
    private int number = 1;
    private final int MAX = 20;

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition oddCondition = lock.newCondition();
    private final Condition evenCondition = lock.newCondition();

    public void printOdd() {
        lock.lock();
        try {
            while (number <= MAX) {
                if (number % 2 == 0) {
                    oddCondition.await();
                }
                System.out.println("Odd: " + number);
                number++;
                evenCondition.signal();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            lock.unlock();
        }
    }

    public void printEven() {
        lock.lock();
        try {
            while (number <= MAX) {
                if (number % 2 != 0) {
                    evenCondition.await();
                }
                System.out.println("Even: " + number);
                number++;
                oddCondition.signal();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            lock.unlock();
        }
    }
}
```

---

## 复盘

这场面试的问题不是技术深度，是**表达和倾听**：

1. **回答太快，没有思考**：很多问题听完就答，没有停顿想一下面试官到底想问什么。

2. **缺乏引导时迷失方向**：一旦问题开放、没有明确引导，就回答得牛头不对马嘴。比如 IO 理解那题，完全没想到 Socket IO。

3. **流水账式表述**：OB 和曙光的收获答得像报菜名，没有重点，没有主线。

4. **概念背诵不熟练**：继承、反射、多态只说"用过"，连基本概念都没说清楚。

5. **没听清问题**：MySQL"对比"使用过，根本没听到"对比"二字。

6. **代码不够优雅**：手写代码能过，但缺少卫语句、边界处理，代码风格不够成熟。

---

## 后续改进

1. **面试节奏**：听完问题停顿 3 秒再答，想清楚面试官想问什么。

2. **结构化表达**：先下结论，再分点展开，最后总结。

3. **概念复习**：基础概念（继承、反射、多态等）要能脱口而出定义 + 作用 + 应用场景。

4. **项目复盘**：每个项目准备"困难 - 解决 - 收获"三段式表述。

5. **代码风格**：手写代码注意卫语句、边界处理、命名规范。

---

这场面试是暑期实习早期的一场，虽然暴露了很多问题，但**还是过了**。表述问题在后续面试中慢慢修正，但当时那种"答非所问、越说越乱"的感觉，到现在还记得。
