---
layout: post
title: "miniob join"
date:   2025-2-23
tags: [miniob，数据库]
comments: true
author: huanghuoguoguo
---

![赛题内容](https://huanghuoguoguo.github.io/images/1724660942296-09bcad46-3dad-47e3-9764-88ebcbf85e44.png)

## Join基本概念

![join的各个形式](https://huanghuoguoguo.github.io/images/1724660842986-c3603f5f-8aaf-4222-ae02-c6159306468c.png)

![join相连形式](https://huanghuoguoguo.github.io/images/1724661101443-7d6343b9-fc9a-4c5b-8a8f-2a44f3c64dbe.png)

在本例子中，只需要实现inner join，也就是内连接即可。

假如是如下语句`select * from t1,t2`，两表会做简单的全量笛卡尔积。但如果是

`select * from t1 join t2 on t1.id = t2.id` 两表根据id连接，和`select * from t1,t2 where t1.id = t2.id`等价。那么我们是不是可以单纯的认为，只是在连接表的过程中，添加了一个predicate？

单表如此，多表连接呢？往下看看。

## 语法分析

要实现 `JOIN` 功能，首先需要修改 `src/observer/sql/parser/` 目录下的文件。这个目录主要负责 SQL 的解析阶段，是整个查询处理流程的起始点。

在引入 `JOIN` 功能时，我们首先要理解 `JOIN` 和 `FROM` 子句之间的关系。以一个典型的 SQL 查询为例：

```sql
SELECT * FROM t1 JOIN t2 ON t1.id = t2.id;
```

在这个查询中，`JOIN` 的作用是将多个表连接起来，并在连接的基础上添加条件。具体来说，`JOIN` 是对 `FROM` 子句中表的笛卡尔积进行筛选，通过指定的条件（如 `t1.id = t2.id`）来过滤出符合条件的记录。如果没有 `JOIN` 条件，`FROM t1, t2` 会产生 `t1` 和 `t2` 的笛卡尔积，而 `JOIN` 则是对这个笛卡尔积进行了优化和筛选。

从更广泛的角度来看，`JOIN` 是一种强大的工具，用于在多个表之间建立关系。它可以是：

1. **内连接（INNER JOIN）**：只返回满足连接条件的记录。
2. **外连接（LEFT JOIN、RIGHT JOIN、FULL JOIN）**：返回一个表的所有记录，以及另一个表中满足条件的记录。
3. **交叉连接（CROSS JOIN）**：返回两个表的笛卡尔积。

不过本赛题只需要实现inner join的功能。

在实现 `JOIN` 功能时，我们需要在解析阶段对 `JOIN` 的语法进行分析，并将其转换为内部的数据结构。这包括：

- **解析** `**JOIN**` **语法**：识别 `JOIN` 关键字、连接的表以及连接条件。
- **构建连接关系**：将参与 `JOIN` 的表及其条件存储到合适的数据结构中，以便后续的查询优化和执行。
- **整合到** `**FROM**` **子句**：将 `JOIN` 的结果作为 `FROM` 子句的一部分，与其他表或子查询一起处理。

通过这种方式，`JOIN` 功能不仅能够高效地连接多个表，还能通过条件过滤减少不必要的数据处理，从而提高查询性能。

### parse_defs.h SqlNode定义

![parse_defs.h添加join相关的数据结构](https://huanghuoguoguo.github.io/images/1724661587917-ad3dbba1-22be-4901-bbb7-cc32d7a086cf.png)

在SelectSqlNode中添加JoinNode的定义，在create_stmt中被使用。

### yacc_sql.y 语法分析树

![添加TOKEN，样例中只有INNER和JOIN](https://huanghuoguoguo.github.io/images/1724660281936-e619c3e4-e073-4300-a0c0-da47d2bc5351.png)![定义](https://huanghuoguoguo.github.io/images/1724660457149-13edc6ec-4022-4fc1-933c-39c7e514452f.png)

![修改select_stmt的语法解析](https://huanghuoguoguo.github.io/images/1724662194076-756a9ad3-8ed9-47f6-b352-9a72a795d33e.png)![添加join](https://huanghuoguoguo.github.io/images/1724662290551-5f36d88a-2402-4610-b657-65c52b4cdd69.png)

在更改完上述代码后，需要在paser目录下执行`sh gen_parser.sh`命令，该命令会输出真正的供引擎使用的代码。

## 词法分析

在解析（resolve）阶段，我们需要修改 `select_stmt` 来收集关于 `JOIN` 的信息。正如之前提到的，`JOIN` 实际上是表的笛卡尔积的一种特殊情况，即两个表的组合。例如，`SELECT * FROM t1, t2` 中的两个表 `t1` 和 `t2` 会被收集到 `relation` 中。那么，当引入 `JOIN` 条件时，这些表是否也应该被收集到 `relation` 中呢？目前来看这样实现比较好，但是不排除有其他的实现。因为 `JOIN` 的本质仍然是表的连接，只是在连接过程中增加了额外的条件约束。

因此，我们可以直接将需要通过 `JOIN` 连接的表推入 `relation` 中，而不是单独处理它们。后续的代码可以统一负责验证和管理这些表的连接关系，包括解析和应用 `JOIN` 条件。这样不仅简化了逻辑，还使得整个解析过程更加一致和高效。

![select_stmt中收集join](https://huanghuoguoguo.github.io/images/1724662998899-d6093298-59a5-42b0-873a-69ff61d78c99.png)

直接将 `JOIN` 需要连接的表推入relation中，统一由后续代码验证和管理。

![收集condition](https://huanghuoguoguo.github.io/images/1724663132601-93c25c6c-5d80-4bee-bb7c-ccf50ba87e64.png)

## 创建逻辑计划

![创建select的逻辑计划时，将关联的表做连接](https://huanghuoguoguo.github.io/images/1724663299260-e51cd4fd-1c06-4674-8a80-c2b311fe97d5.png)

解释一下这里的代码。假如语句是这样的`select * from t1,t2`

那么其创建的逻辑计划是这样的。

![生成的逻辑算子示意图](https://huanghuoguoguo.github.io/images/1724663459632-be271df7-6d45-485e-af91-7a7df8d45168.png)

如果是`select * from t1 join t2 on t1.id = t2.id`，那么逻辑计划是这样的。

![生成的逻辑算子图](https://huanghuoguoguo.github.io/images/1724663740378-2fe7ce5e-d206-4ff6-800d-324e6c4699f8.png)

如果是多表连接呢？`select * from t1 join t2 on t1.id = t2.id join t3 on t3.id = t2.id`



![img](https://huanghuoguoguo.github.io/images/1724664087141-4747f4da-153b-4fd1-955a-b66e08193761.png)

对多个表连接的情况，需要一个一个表连接，然后再将连接后的表(join_tuple)作为类似于临时表的形式，再和下一个表连接。

如果再加上where条件呢？`select * from t1 join t2 on t1.id = t2.id join t3 on t3.id = t2.id where t1.id > 1`，那么此时在创建逻辑计划的阶段创建的是：

![img](https://huanghuoguoguo.github.io/images/1724665642673-c7db8f1b-d7a1-4715-99d3-654774c2c097.png)

在当前阶段生成的逻辑计划存在一些问题，这些问题会直接影响到后续物理计划的执行效率。例如，按照当前的逻辑，执行步骤是这样的：首先从底层执行 `table_get_t1` 和 `table_get_t2`，将它们连接后再与 `t3` 连接，最后才执行 `t1.id` 的过滤条件。这种执行顺序显然不够高效。对于条件如 `t1.id <= 1`，如果在连接之前就能过滤掉不满足条件的记录，那么后续的连接操作将大大减少不必要的笛卡尔积计算。因此，优化这种执行顺序是我们首先需要考虑的问题。

那么，我们有哪些优化方案呢？

1. **在语句创建阶段将条件绑定并下沉**
   这种方法的思路是在语句构建阶段直接将过滤条件绑定到对应的表上。然而，目前还没有想到一个理想的实现方式，因此暂时搁置。
2. **将** `**JOIN**` **的过滤条件放入普通过滤条件中**
   在创建逻辑计划时，将 `JOIN` 的过滤条件（`join_filter`）与普通过滤条件合并，并将其绑定到 `table_get` 操作上。这样可以在逻辑计划阶段就将条件应用到表的扫描过程中，从而减少不必要的数据处理。
3. **在优化阶段将** `**WHERE**` **条件下沉到** `**table_get**` **中**
   这种方法的核心是在优化阶段将 `WHERE` 条件直接下沉到 `table_get` 操作中。这样可以确保在扫描表时直接应用过滤条件，从而减少不必要的数据读取和处理。

经过综合考虑，我们最终选择了在优化阶段将条件下沉的方案。然而，在现有的下沉逻辑中，只有当 `predicate` 直接绑定到 `table_get` 时，才能进行条件下沉。例如，在查询 `SELECT * FROM t1 WHERE t1.id > 1` 中，`predicate` 直接绑定到 `table_get`，因此可以顺利下沉。为了在优化阶段也能实现条件下沉，我们需要对这一条件进行扩展，将可下沉的 `predicate` 条件推广到所有子节点。

通过这种方式，我们可以在优化阶段更灵活地将条件下沉到表扫描操作中，从而提高查询的执行效率。

![img](https://huanghuoguoguo.github.io/images/1724669431993-fed020ba-1ae0-43f4-adc0-5dbd2407b444.png)

在实现 `JOIN` 功能的过程中，我们首先在 YACC 中收集 `JOIN` 相关的信息，并在语句（`stmt`）构建阶段将参与 `JOIN` 的表放入连接表中。这一过程虽然能够生成逻辑计划，但生成的逻辑计划复杂度较高，难以通过大数据量的测试用例。这是因为在这种情况下，`JOIN` 操作的执行顺序和过滤条件的应用时机并不理想，导致了不必要的计算和资源浪费。

为了解决这一问题，我们在优化阶段引入了一种策略：将最外层的 `WHERE` 条件按需下沉至扫表（`table_get`）阶段。通过这种方式，我们可以在扫描表时直接应用过滤条件，从而减少不必要的数据读取和处理，显著降低逻辑计划的复杂度。这种优化策略的核心在于将过滤条件尽早应用于数据扫描过程中，避免了在连接操作之后再进行过滤，从而减少了不必要的笛卡尔积计算。

这种优化方法不仅提高了查询的执行效率，还使得逻辑计划能够更好地应对大数据量的场景。通过在优化阶段对条件进行下沉，我们能够灵活地调整执行计划，确保查询操作在性能和资源利用上达到最优。

思路如此，具体操作的代码需要和rewriter中的改写规则结合来看。

```cpp
RC PredicatePushdownRewriter::try_rewrite_join(std::unique_ptr<LogicalOperator> &oper,
    std::unique_ptr<Expression> &                                                predicate_expr,
    bool &                                                                       change_made
    )
{
  RC    rc        = RC::SUCCESS;
  auto &childrens = oper->children();
  for (auto &child : childrens) {
    // 如果孩子是table_get，则进行判断，是否可以进行下沉。
    if (child->type() == LogicalOperatorType::TABLE_GET) {
      rc = try_rewriter_table_get(predicate_expr, change_made, child);
      if (rc != RC::SUCCESS)
        return rc;
    } else {
      // 不是，继续下沉。
      rc = try_rewrite_join(child, predicate_expr, change_made);
      if (rc != RC::SUCCESS)
        return rc;
    }
  }
  return rc;
}
```

关键代码是尝试进行condition下沉。具体可以从非join情况下的下沉理解。
