---
layout: post
title: "OceanBase索引，分布式数据存储"
date:   2025-1-5
tags: [OceanBase, 数据库, 底层]
comments: true
author: huanghuoguoguo
---

mysql通过分库分表可以实现数据的分片。像原生分布式数据库是怎么分片的呢？像oceanbase或者polardb，不需要额外的配置就实现了分片和复制，是怎么处理数据的呢？像mysql的分库分表，可以认为是做了主键的均匀hash进行映射，到表上，相当于做了一个前置hash索引，将键路由到存储数据的表上，那么原生分布式数据库怎么做索引的呢？因为他需要实现数据的自动获取或者命中索引，还是说每个节点都存储了该表的所有索引，然后查询的时候，回表的时候，如果在当前节点上就直接获取，不在当前节点就会进行转发最后再汇总？

<font style="color:rgb(6, 6, 7);">在分布式数据库中，分片（Sharding）是一种常见的技术，用于将数据分布到多个节点上，以提高系统的扩展性和性能。与传统的 MySQL 分库分表类似，原生分布式数据库（如 OceanBase 和 PolarDB）通过更高级的分片机制实现了数据的自动管理和高效查询。以下是这些数据库如何处理分片和索引的详细解释：</font>

---

### **<font style="color:rgb(6, 6, 7);">MySQL 分库分表与原生分布式数据库的分片机制</font>**
#### **<font style="color:rgb(6, 6, 7);">MySQL 分库分表</font>**
<font style="color:rgb(6, 6, 7);">在 MySQL 中，分库分表是一种常见的水平扩展策略。例如，可以通过对主键进行哈希映射，将数据均匀分配到多个表或数据库中</font><font style="color:rgb(6, 6, 7);">。这种方式类似于在应用层实现了一个简单的分片机制，但需要开发者手动管理分片逻辑和查询路由。</font>

#### **<font style="color:rgb(6, 6, 7);">OceanBase 的分片机制</font>**
<font style="color:rgb(6, 6, 7);">OceanBase 是一种原生分布式数据库，它通过更高级的分片策略实现数据的自动管理和高效查询</font><font style="color:rgb(6, 6, 7);">：</font>

1. **<font style="color:rgb(6, 6, 7);">数据分片（Tablet）</font>**<font style="color:rgb(6, 6, 7);">：OceanBase 将大表划分为多个较小的分片（tablet），每个分片由多个节点共同管理。这种方式不仅提高了数据处理的并行性，还通过分布式架构实现了负载均衡</font><font style="color:rgb(6, 6, 7);">。</font>
2. **<font style="color:rgb(6, 6, 7);">哈希分片与范围分片</font>**<font style="color:rgb(6, 6, 7);">：OceanBase 支持基于哈希和范围的分片策略。哈希分片通过对数据的关键属性进行哈希运算，将数据均匀分布到不同节点；范围分片则根据数据的范围划分，适合有序数据的访问</font><font style="color:rgb(6, 6, 7);">。</font>
3. **<font style="color:rgb(6, 6, 7);">索引管理</font>**<font style="color:rgb(6, 6, 7);">：OceanBase 在每个节点上维护局部索引，查询时会根据分片键直接定位到目标节点。如果查询涉及多个分片，OceanBase 会自动协调跨节点的查询，并在必要时进行数据汇总</font><font style="color:rgb(6, 6, 7);">。</font>

#### **<font style="color:rgb(6, 6, 7);">PolarDB 的分片机制</font>**
<font style="color:rgb(6, 6, 7);">PolarDB 是另一种云原生分布式数据库，它通过以下方式实现分片</font><font style="color:rgb(6, 6, 7);">：</font>

1. **<font style="color:rgb(6, 6, 7);">哈希分片</font>**<font style="color:rgb(6, 6, 7);">：PolarDB 支持通过哈希函数对数据进行分片，例如使用 </font>`DBDISTRIBUTION BY HASH(id)`<font style="color:rgb(6, 6, 7);"> 将数据均匀分布到多个节点</font><font style="color:rgb(6, 6, 7);">。</font>
2. **<font style="color:rgb(6, 6, 7);">索引优化</font>**<font style="color:rgb(6, 6, 7);">：PolarDB 采用了优化的索引结构（如 Lizard B+tree），通过智能分片和缓存优化减少跨节点查询的开销</font><font style="color:rgb(6, 6, 7);">。</font>
3. **<font style="color:rgb(6, 6, 7);">动态调整</font>**<font style="color:rgb(6, 6, 7);">：PolarDB 能够根据查询模式动态调整数据分片策略，确保查询效率最大化</font><font style="color:rgb(6, 6, 7);">。</font>

#### **<font style="color:rgb(6, 6, 7);">索引管理与查询优化</font>**
<font style="color:rgb(6, 6, 7);">在原生分布式数据库中，索引的管理方式与传统数据库有所不同：</font>

1. **<font style="color:rgb(6, 6, 7);">局部索引与全局索引</font>**<font style="color:rgb(6, 6, 7);">：每个节点上维护局部索引，用于快速定位数据。对于跨节点的查询，数据库会自动协调并汇总结果</font><font style="color:rgb(6, 6, 7);">。</font>
2. **<font style="color:rgb(6, 6, 7);">智能路由</font>**<font style="color:rgb(6, 6, 7);">：查询时，数据库会根据分片键直接定位到目标节点，避免不必要的数据传输</font><font style="color:rgb(6, 6, 7);">。</font>
3. **<font style="color:rgb(6, 6, 7);">优化策略</font>**<font style="color:rgb(6, 6, 7);">：通过自适应分支因子、异步写入和数据压缩等技术，进一步提升索引的性能。</font>

<font style="color:rgb(6, 6, 7);">与 MySQL 的分库分表相比，原生分布式数据库（如 OceanBase 和 PolarDB）通过更高级的分片机制实现了数据的自动管理和高效查询。这些数据库不仅支持多种分片策略（如哈希分片和范围分片），还通过局部索引和智能路由优化查询性能。此外，它们还具备动态调整分片和索引的能力，以适应不同的数据访问模式</font><font style="color:rgb(6, 6, 7);">。</font>

<font style="color:rgb(6, 6, 7);">这种自动化的分片和索引管理机制，使得原生分布式数据库在处理大规模数据时更加高效和灵活，无需开发者手动配置和管理分片逻辑。</font>

#### <font style="color:rgb(24, 24, 24) !important;">主键选择</font>
<font style="color:rgb(38, 38, 38);">对主键来说，要保证在所有分片中都唯一，它本质上就是一个全局唯一的索引。如果用大部分同学喜欢的自增作为主键，就会发现存在很大的问题。</font>

<font style="color:rgb(38, 38, 38);">因为自增并不能在插入前就获得值，而是要通过填 NULL 值，然后再通过函数 last_insert_id()获得自增的值。所以，如果在每个分片上通过自增去实现主键，可能会出现同样的自增值存在于不同的分片上。</font>

<font style="color:rgb(38, 38, 38);">比如，对于电商的订单表 orders，其表结构如下（分片键是o_custkey，表的主键是o_orderkey）：</font>

```plain
CREATE TABLE `orders` (
  `O_ORDERKEY` int NOT NULL auto_increment,
  `O_CUSTKEY` int NOT NULL,
  `O_ORDERSTATUS` char(1) NOT NULL,
  `O_TOTALPRICE` decimal(15,2) NOT NULL,
  `O_ORDERDATE` date NOT NULL,
  `O_ORDERPRIORITY` char(15) NOT NULL,
  `O_CLERK` char(15) NOT NULL,
  `O_SHIPPRIORITY` int NOT NULL,
  `O_COMMENT` varchar(79) NOT NULL,
  PRIMARY KEY (`O_ORDERKEY`),
  KEY (`O_CUSTKEY`)
  ......
) ENGINE=InnoDB
```

<font style="color:rgb(38, 38, 38);">如果把 o_orderkey 设计成上图所示的自增，那么很可能 o_orderkey 同为 1 的记录在不同的分片出现，如下图所示：</font>

![](https://cdn.nlark.com/yuque/0/2025/webp/32754462/1737635380432-03dfb2cd-6dc5-4023-a4f9-c1bb749d8036.webp)

**<font style="color:rgb(38, 38, 38);">所以，在分布式数据库架构下，尽量不要用自增作为表的主键</font>**<font style="color:rgb(38, 38, 38);">：自增性能很差、安全性不高、不适用于分布式架构。</font>

<font style="color:rgb(38, 38, 38);">讲到这儿，我们已经说明白了“自增主键”的所有问题，那么该如何设计主键呢？依然还是用全局唯一的键作为主键，比如 MySQL 自动生成的有序 UUID；业务生成的全局唯一键（比如发号器）；或者是开源的 UUID 生成算法，比如雪花算法（但是存在时间回溯的问题）。</font>

<font style="color:rgb(38, 38, 38);">总之，</font>**<font style="color:rgb(38, 38, 38);">用有序的全局唯一替代自增，是这个时代数据库主键的主流设计标准</font>**<font style="color:rgb(38, 38, 38);">，如果你还停留在用自增做主键，或许代表你已经落后于时代发展了。</font>

#### <font style="color:rgb(24, 24, 24) !important;">索引设计</font>
<font style="color:rgb(38, 38, 38);">通过分片键可以把 SQL 查询路由到指定的分片，但是在现实的生产环境中，业务还要通过其他的索引访问表。</font>

<font style="color:rgb(38, 38, 38);">还是以前面的表 orders 为例，如果业务还要根据 o_orderkey 字段进行查询，比如查询订单 ID 为 1 的订单详情：</font>

<font style="color:rgb(89, 89, 89);background-color:rgb(249, 249, 249);">SELECT * FROM orders WHERE o_orderkey = 1</font>

<font style="color:rgb(38, 38, 38);">我们可以看到，由于分片规则不是分片键，所以需要查询 4 个分片才能得到最终的结果，如果下面有 1000 个分片，那么就需要执行 1000 次这样的 SQL，这时性能就比较差了。</font>

<font style="color:rgb(38, 38, 38);">但是，我们知道 o_orderkey 是主键，应该只有一条返回记录，也就是说，o_orderkey 只存在于一个分片中。这时，可以有以下两种设计：</font>

+ <font style="color:rgb(38, 38, 38);">同一份数据，表 orders 根据 o_orderkey 为分片键，再做一个分库分表的实现；</font>
+ <font style="color:rgb(38, 38, 38);">在索引中额外添加分片键的信息。</font>

<font style="color:rgb(38, 38, 38);">这两种设计的本质都是通过冗余实现空间换时间的效果，否则就需要扫描所有的分片，当分片数据非常多，效率就会变得极差。</font>

<font style="color:rgb(38, 38, 38);">而第一种做法通过对表进行冗余，对于 o_orderkey 的查询，只需要在 o_orderkey = 1的分片中直接查询就行，效率最高，但是设计的缺点又在于冗余数据量太大。</font>

<font style="color:rgb(38, 38, 38);">所以，改进的做法之一是实现一个</font>**<font style="color:rgb(38, 38, 38);">索引表</font>**<font style="color:rgb(38, 38, 38);">，表中只包含 o_orderkey 和分片键 o_custkey，如：</font>

```plain
CREATE TABLE idx_orderkey_custkey （
  o_orderkey INT
  o_custkey INT,
  PRIMARY KEY (o_orderkey)
)
```

<font style="color:rgb(38, 38, 38);">如果这张索引表很大，也可以将其分库分表，但是它的分片键是 o_orderkey，如果这时再根据字段 o_orderkey 进行查询，可以进行类似二级索引的回表实现：先通过查询索引表得到记录 o_orderkey = 1 对应的分片键 o_custkey 的值，接着再根据 o_custkey 进行查询，最终定位到想要的数据，如：</font>

```plain
SELECT * FROM orders WHERE o_orderkey = 1
=>
# step 1
SELECT o_custkey FROM idx_orderkey_custkey 
WHERE o_orderkey = 1
# step 2
SELECT * FROM orders 
WHERE o_custkey = ? AND o_orderkey = 1
```

<font style="color:rgb(38, 38, 38);">这个例子是将一条 SQL 语句拆分成 2 条 SQL 语句，但是拆分后的 2 条 SQL 都可以通过分片键进行查询，这样能保证只需要在单个分片中完成查询操作。不论有多少个分片，也只需要查询 2个分片的信息，这样 SQL 的查询性能可以得到极大的提升。</font>

<font style="color:rgb(38, 38, 38);">通过</font>**<font style="color:rgb(38, 38, 38);">索引表</font>**<font style="color:rgb(38, 38, 38);">的方式，虽然存储上较冗余全表容量小了很多，但是要根据另一个分片键进行数据的存储，依然显得不够优雅。</font>

<font style="color:rgb(38, 38, 38);">因此，最优的设计，不是创建一个索引表，而是将分片键的信息保存在想要查询的列中，这样通过查询的列就能直接知道所在的分片信息。</font>

<font style="color:rgb(38, 38, 38);">如果我们将订单表 orders 的主键设计为一个字符串，这个字符串中最后一部分包含分片键的信息，如：</font>

<font style="color:rgb(89, 89, 89);background-color:rgb(249, 249, 249);">o_orderkey = string（o_orderkey + o_custkey）</font>

<font style="color:rgb(38, 38, 38);">那么这时如果根据 o_orderkey 进行查询：</font>

```plain
SELECT * FROM Orders
WHERE o_orderkey = '1000-1';
```

<font style="color:rgb(38, 38, 38);">由于字段 o_orderkey 的设计中直接包含了分片键信息，所以我们可以直接知道这个订单在分片1 中，直接查询分片 1 就行。</font>

<font style="color:rgb(38, 38, 38);">同样地，在插入时，由于可以知道插入时 o_custkey 对应的值，所以只要在业务层做一次字符的拼接，然后再插入数据库就行了。</font>

<font style="color:rgb(38, 38, 38);">这样的实现方式较冗余表和索引表的设计来说，效率更高，查询可以提前知道数据对应的分片信息，只需 1 次查询就能获取想要的结果。</font>

<font style="color:rgb(38, 38, 38);">这样实现的缺点是，主键值会变大一些，存储也会相应变大。但只要主键值是有序的，插入的性能就不会变差。而通过在主键值中保存分片信息，却可以大大提升后续的查询效率，这样空间换时间的设计，总体上看是非常值得的。</font>

<font style="color:rgb(38, 38, 38);">当然，这里我们谈的设计都是针对于唯一索引的设计，如果是非唯一的二级索引查询，那么非常可惜，依然需要扫描所有的分片才能得到最终的结果，如：</font>

```plain
SELECT * FROM Orders
WHERE o_orderate >= ? o_orderdate < ?
```

<font style="color:rgb(38, 38, 38);">因此，再次提醒你，分布式数据库架构设计的要求是</font>**<font style="color:rgb(38, 38, 38);">业务的绝大部分请求能够根据分片键定位到 1 个分片上。</font>**

<font style="color:rgb(38, 38, 38);">如果业务大部分请求都需要扫描所有分片信息才能获得最终结果，那么就不适合进行分布式架构的改造或设计。</font>

<font style="color:rgb(38, 38, 38);">最后，我们再来回顾下淘宝用户订单表的设计：</font>

![](https://cdn.nlark.com/yuque/0/2025/webp/32754462/1737635380717-c9faa354-6678-4b3f-a39b-c66d8371d848.webp)

<font style="color:rgb(38, 38, 38);">上图是我的淘宝订单信息，可以看到，订单号的最后 6 位都是 308113，所以可以大概率推测出：</font>

+ <font style="color:rgb(38, 38, 38);">淘宝订单表的分片键是用户 ID；</font>
+ <font style="color:rgb(38, 38, 38);">淘宝订单表，订单表的主键包含用户 ID，也就是分片信息。这样通过订单号进行查询，可以获得分片信息，从而查询 1 个分片就能得到最终的结果。</font>

#### <font style="color:rgb(24, 24, 24) !important;">全局表</font>
<font style="color:rgb(38, 38, 38);">在分布式数据库中，有时会有一些无法提供分片键的表，但这些表又非常小，一般用于保存一些全局信息，平时更新也较少，绝大多数场景仅用于查询操作。</font>

<font style="color:rgb(38, 38, 38);">例如 tpch 库中的表 nation，用于存储国家信息，但是在我们前面的 SQL 关联查询中，又经常会使用到这张表，对于这种全局表，可以在每个分片中存储，这样就不用跨分片地进行查询了。如下面的设计：</font>

![](https://cdn.nlark.com/yuque/0/2025/webp/32754462/1737635380648-9406a506-ea76-4e5b-a0f5-abbae44e932d.webp)

#### <font style="color:rgb(24, 24, 24) !important;">唯一索引</font>
<font style="color:rgb(38, 38, 38);">最后我们来谈谈唯一索引的设计，与主键一样，如果只是通过数据库表本身唯一约束创建的索引，则无法保证在所有分片中都是唯一的。</font>

<font style="color:rgb(38, 38, 38);">所以，在分布式数据库中，唯一索引一样要通过类似主键的 UUID 的机制实现，用全局唯一去替代局部唯一，但实际上，即便是单机的 MySQL 数据库架构，我们也推荐使用全局唯一的设计。因为你不知道，什么时候，你的业务就会升级到全局唯一的要求了。</font>

#### <font style="color:rgb(24, 24, 24) !important;">总结</font>
<font style="color:rgb(38, 38, 38);">今天介绍了非常重要的分布式数据库索引设计，内容非常干货，是分布式架构设计的重中之重，建议反复阅读，抓住本文的重点，总结来说：</font>

+ <font style="color:rgb(38, 38, 38);">分布式数据库主键设计使用有序 UUID，全局唯一；</font>
+ <font style="color:rgb(38, 38, 38);">分布式数据库唯一索引设计使用 UUID 的全局唯一设计，避免局部索引导致的唯一问题；</font>
+ <font style="color:rgb(38, 38, 38);">分布式数据库唯一索引若不是分片键，则可以在设计时保存分片信息，这样查询直接路由到一个分片即可；</font>
+ <font style="color:rgb(38, 38, 38);">对于分布式数据库中的全局表，可以采用冗余机制，在每个分片上进行保存。这样能避免查询时跨分片的查询。</font>

