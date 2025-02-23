---
layout: post
title: "miniob date"
date:   2025-2-23
tags: [miniob，数据库]
comments: true
author: huanghuoguoguo
---

![题目描述](https://huanghuoguoguo.github.io/images/1740120389366-dab53329-b6a1-4077-824d-637a4df867f9.png)

# 配置环境

1. 作为实现的第一个题目，我们先来配置下clion的debug设置，（先去看部署篇，将远程开发部署的设置好）

![编辑运行选项](https://huanghuoguoguo.github.io/images/1739847084967-c5229cba-ffe5-42b6-a2b5-583c17dd70ae.png)，

点击进入之后按照正确的规则配置，需要控制台的启动程序为build_debug下的observer。

![运行/调试配置图](https://huanghuoguoguo.github.io/images/1739847306310-ad4c13bf-19a0-4b47-b328-6535ce08a155.png)



`./bin/observer -f ../etc/observer.ini -P cli`，具体的编译脚本设置如下，这样就做好了每次运行前重新编译并运行最新版本的准备

![编辑工具，这里按照自己对应的配置进行编辑](https://huanghuoguoguo.github.io/images/1739847358976-6a905fad-ff37-426c-a393-5c3e87b5083a.png)

# Date实现

添加日期类型（Date）为数据库提供了存储和处理日期信息的能力。通过实现Date数据类型，可以支持用户在数据库中输入、存储和查询日期值。服务器接收到客户端发出的SQL指令时，必须通过网络模块将该指令传送至解析模块，将SQL字符串转换为服务器可以理解的数据结构形式，这样数据库才能对这些指令进行操作和处理。

## lex词法分析

在为数据库添加日期类型（Date）时，需要为数据库提供存储和处理日期值的功能。为了实现这一点，首先需要在解析词法规则的 `lex_sql.l` 文件中进行相应的定义。![添加lex_sql.l中的token识别](https://huanghuoguoguo.github.io/images/1739849772122-03baadc0-002f-4fc8-a851-88500643c738.png)

根据现有类型（如 `int` 和 `float`）的定义，我们需要为日期类型添加类似的词法规则，以便在语法分析时识别日期字符串并返回 `DATE_STR` 这一特定的 token。这一过程需要用到正则表达式，虽然编写规则可能较为复杂，但其原理是通过对字符串模式的匹配，来识别出符合日期格式的输入。

```cpp
{QUOTE}([0-9]{4})\-([0-9]|[0-9]{2})\-([0-9]|[0-9]{2}){QUOTE} yylval->string=strdup(yytext); RETURN_TOKEN(DATE_STR);
```

![粘贴正则表达式](https://huanghuoguoguo.github.io/images/1739849953423-11caaf34-4168-46ea-9b3f-9491f09204d5.png)

miniob 将所有用到的类型分类存储在 `src/observer/common/type` 目录下。这些类型定义在数据库的类型比较等后续操作中会发挥作用。在定义好词法规则后，接下来需要对语法规则（YACC）进行定义。YACC 的作用是基于 `lex` 定义的 token 来解析 SQL，创建对应的数据结构，只有这样才能在后续的模块中对这些数据结构进行进一步的操作。然而，在这一步骤中，目前尚未定义 date 类型的结构。因此，我们可以参考 integer 类型的实现方式，对 date 类型进行仿写，以创建其内部数据结构。

![在type中新增Date类型枚举](https://huanghuoguoguo.github.io/images/1739856362997-8a577286-e50d-451c-828b-3b7ac552f85d.png)

![在类池中增加DateType](https://huanghuoguoguo.github.io/images/1739855550842-cd53b564-c704-45f1-a01c-b73a3534e6e1.png)

## 创建date_type类

查看其他类的实现，integer，float等都继承了一个基类DataType。虽然暂时还不知道他是怎么被用到的，但是我们可以知道date和int应该是同一层级的类型。

![DataType基类方法](https://huanghuoguoguo.github.io/images/1739950952233-c2881776-e607-4acd-a566-b9bec6307b28.png)

虽然都给了默认实现，但是date主要要求实现这几个方法。

```cpp
// 比较两个Value
int compare(const Value &left, const Value &right) const override;
// 从字符串转Value
RC set_value_from_str(Value &val, const string &data) const override;
// Value转字符串
RC to_string(const Value &val, string &result) const override;
```

## Value

顺便提一下Value，在miniob内部是对一段字节地址、内容封装的类。定义了一系列获取值，加减法，乘除法等等。

![Value持有的数据](https://huanghuoguoguo.github.io/images/1739951406497-f2efc490-9555-4ef1-8a3d-6bacb7ffd739.png)

每个Value对象都在内部维护了一个union Val，这里指向了真正的数据的内存地址。其他的方法都是为这段地址服务的。

它们之间不是无用的封装，而是相互配合的关系。`Value` 是对基本类型（如 `int`、`float`、`char*` 等）数据的一层封装，它定义了如何存储和访问这些基本类型的数据。而 `DataType` 则可以理解为一种行为规范，它接受 `Value` 参数，并从 `Value` 中提取原始数据，按照定义的行为进行操作。

## DateType实现

既然都要继承DataType，那日期类型也继承一下吧。至于他的方法之后会在哪里被使用，我们暂且不关注。

```cpp
//
// Created by bob on 24-9-16.
//

#pragma once

#include <common/log/log.h>

#include "common/rc.h"
#include "common/type/data_type.h"

/**
 * @brief 日期类型
 * @ingroup DataType
 */
//继承通用的DataType类型
class DateType : public DataType {
public:
DateType() : DataType(AttrType::DATES) {
}

virtual ~DateType() = default;
//用于日期的验证，验证给定的年月日是否有效，考虑闰年。
static bool check_dateV2(int year, int month, int day) {
    static int mon[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    LOG_WARN("check_dateV2: year %d,month %d,day %d");
    bool leap = (year % 400 == 0 || (year % 100 && year % 4 == 0));
    if (year > 0 && (month > 0) && (month <= 12) && (day > 0) && (
        day <= ((month == 2 && leap) ? 1 : 0) + mon[month]))
        return true;
    else
        return false;
}
//将日期字符串转换为整数格式，格式为 YYYYMMDD，无效日期返回 -1。
static int string_to_date(const std::string &str, int32_t &date) {
    int y, m, d;
    sscanf(str.c_str(), "%d-%d-%d", &y, &m, &d); //not check return value eq 3, lex guarantee
    bool b = check_dateV2(y, m, d);
    if (!b) return -1;
    date = y * 10000 + m * 100 + d;
    return 0;
}
//将整数格式的日期转换为字符串格式 YYYY-MM-DD。
static std::string date_to_string(int32_t date) {
    std::string ans = "YYYY-MM-DD";
    std::string tmp = std::to_string(date);
    int tmp_index = 7;
    for (int i = 9; i >= 0; i--) {
        if (i == 7 || i == 4) {
            ans[i] = '-';
        } else {
            ans[i] = tmp[tmp_index--];
        }
    }
    return ans;
}

int compare(const Value &left, const Value &right) const override;

RC set_value_from_str(Value &val, const string &data) const override;

RC to_string(const Value &val, string &result) const override;
};
//
// Created by bob on 24-9-16.
//
#include "common/lang/comparator.h"
#include "common/lang/sstream.h"
#include "common/log/log.h"
#include "common/type/date_type.h"
#include "common/value.h"

RC DateType::to_string(const Value &val, string &result) const
{
    std::stringstream ss;

    int32_t int_value = val.value_.int_value_;
    std::string       ans       = "YYYY-MM-DD";
    std::string       tmp       = std::to_string(int_value);
    int               tmp_index = 7;
    for (int i = 9; i >= 0; i--) {
        if (i == 7 || i == 4) {
            ans[i] = '-';
        } else {
            ans[i] = tmp[tmp_index--];
        }
    }
    ss << ans;

    result = ss.str();
    return RC::SUCCESS;
}

int DateType::compare(const Value &left, const Value &right) const
{   if (left.attr_type() == AttrType::DATES && right.attr_type() == AttrType::DATES)
    return common::compare_int((void *)&left.value_.int_value_, (void *)&right.value_.int_value_);

    return INT32_MAX;
}

RC DateType::set_value_from_str(Value &val, const string &data) const
{
    RC                rc = RC::SUCCESS;
    stringstream deserialize_stream;
    deserialize_stream.clear();  // 清理stream的状态，防止多次解析出现异常
    deserialize_stream.str(data);
    int int_value;
    deserialize_stream >> int_value;
    if (!deserialize_stream || !deserialize_stream.eof()) {
        rc = RC::SCHEMA_FIELD_TYPE_MISMATCH;
    } else {
        val.set_int(int_value);
    }
    return rc;
}
```

上面的几个成员函数，就维护了date类型的行为。

## yacc语法分析

去yacc文件中，将词法解析出来的token与date数据结构进行解析绑定。

![yacc文件引入头文件](https://huanghuoguoguo.github.io/images/1739855992162-637d1767-8615-458d-ab81-e279dc0c4ee2.png)

yacc的编写是有一套规则的，这里我们不解释为什么这么写，只是仿照其他类型（int）的实现，同时在过程中体会猜测他的行为。当遇到问题的时候再去了解yacc的规则，否则篇幅太长。

![增加token标识符，这里为什么是_T，也是和原来保持一致。](https://huanghuoguoguo.github.io/images/1739856033383-236b0eb1-2095-44c2-8d99-6edbee8ec583.png)

![DATE_STR被认为是string类型的](https://huanghuoguoguo.github.io/images/1739856149572-fb9c2c67-5e49-4359-9ca1-62f40f14c918.png)

这里可以看到在type中date应该和其他int、float是同一层级的元素。在yacc中，都是类似一个树形的结构，匹配到哪里能正确结束，就返回成功。

![attr_info](https://huanghuoguoguo.github.io/images/1739952994583-b96f12f9-eb61-4476-9cbc-c98482513c40.png)

yacc按照一定规则解析。`|`代表或的意思。

![type可以匹配int，string等](https://huanghuoguoguo.github.io/images/1739856224712-4b0ecea8-4301-4468-b0af-6788ab74527a.png)

这样词语法解析工作就完成了，服务端可以解析到date类型，解析出来的sql内容会放在sqlnode中，递交给解析statement的代码。![CreateTable可以拿到sqlnode，sqlnode中的attr_info是元数据信息](https://huanghuoguoguo.github.io/images/1739859525535-2251ff75-d139-4441-8617-fa811479eb6e.png)

# 测试是否正确识别

使用create table建表语句进行测试，已经绑定成功![测试能否在sql_node中获取到信息](https://huanghuoguoguo.github.io/images/1739857233284-d55a2957-b014-4575-9a79-8cf05eb09630.png)

使用insert插入语句进行测试，在ob官网的训练营中，date题目的测试集样例会有将int类型的数据插入放到date类型，因此我们需要在插入的时候检查插入数据类型是否与表属性类型一致

点击进入

![create statement](https://huanghuoguoguo.github.io/images/1739859554360-d335b15a-9f79-41fd-985b-53be5ab3a0db.png)

![代码逻辑](https://huanghuoguoguo.github.io/images/1739859852102-1c85e642-4d65-4190-9fc1-c2aba2d65411.png)

```cpp
RC InsertStmt::create(Db *db, const InsertSqlNode &inserts, Stmt *&stmt)
{
    const char *table_name = inserts.relation_name.c_str();
    if (nullptr == db || nullptr == table_name || inserts.values.empty()) {
        LOG_WARN("invalid argument. db=%p, table_name=%p, value_num=%d",
            db, table_name, static_cast<int>(inserts.values.size()));
        return RC::INVALID_ARGUMENT;
    }

    // check whether the table exists
    Table *table = db->find_table(table_name);
    if (nullptr == table) {
        LOG_WARN("no such table. db=%s, table_name=%s", db->name(), table_name);
        return RC::SCHEMA_TABLE_NOT_EXIST;
    }

    // check the fields number
    const Value     *values     = inserts.values.data();
    const int        value_num  = static_cast<int>(inserts.values.size());
    const TableMeta &table_meta = table->table_meta();
    const int        field_num  = table_meta.field_num() - table_meta.sys_field_num();
    if (field_num != value_num) {
        LOG_WARN("schema mismatch. value num=%d, field num in schema=%d", value_num, field_num);
        return RC::SCHEMA_FIELD_MISSING;
    }
    // check fields type
    const int sys_field_num = table_meta.sys_field_num();
    for (int i = 0; i < value_num; i++) {
        const FieldMeta *field_meta = table_meta.field(i + sys_field_num);
        const AttrType field_type = field_meta->type();
        const AttrType value_type = values[i].attr_type();
        if (field_type != value_type) {  // TODO try to convert the value type to field type
            LOG_WARN("field type mismatch. table=%s, field=%s, field type=%d, value_type=%d",
                table_name, field_meta->name(), field_type, value_type);
            return RC::SCHEMA_FIELD_TYPE_MISMATCH;
        }
    }
    // everything alright
    stmt = new InsertStmt(table, values, value_num);
    return RC::SUCCESS;
}
```

接下来进入查询优化阶段，创建逻辑计划和创建物理计划。逻辑计划主要用于表达查询的语义，进行查询的逻辑优化等，例如where条件下推，子查询的展开，不关心具体的物理执行方式，而物理计划就是进行具体执行方式的生成，但是这里并没有涉及到接下来的步骤，因为我们只是新增了数据库表字段的数据类型，因此在这里我们只是熟悉下流程

进入查询优化阶段，点击进入。

![进入查询优化](https://huanghuoguoguo.github.io/images/1739857595648-cd7c255d-6b4b-4e98-9375-90f35ec2b6dc.png)![stage](https://huanghuoguoguo.github.io/images/1739857704667-38707cf1-7b85-41a4-90ca-7cff1c305341.png)

点击进入创建逻辑计划。

![创建逻辑计划](https://huanghuoguoguo.github.io/images/1739857741259-d3e62ca5-267f-4ff3-9a95-71b9c40d4a73.png)

会根据type 走相应的语句分支。

![创建statement](https://huanghuoguoguo.github.io/images/1739857810425-aed71474-541f-4dc2-9aab-21ea0db621db.png)

 在 MiniOB（以及大多数数据库系统）中，**创建表（CREATE TABLE）语句不会生成逻辑计划和物理计划**。

逻辑计划和物理计划用于查询优化和执行

逻辑计划（Logical Plan）和物理计划（Physical Plan）主要用于 **查询语句（如 SELECT, UPDATE, DELETE）**，因为这些语句需要：

- **查询优化**（如选择最优的索引、连接顺序等）。
- **决定执行方式**（如索引扫描 vs. 全表扫描）。

而 `CREATE TABLE` 是 **DDL（Data Definition Language，数据定义语言）** 语句，**不涉及数据查询或优化**，而是直接 **修改数据库的元数据（metadata）**，所以不需要逻辑计划或物理计划。

执行物理计划，但是上一步骤没有生成物理计划，因此这一步啥也不做。





# 总结

综上所述，在实现新增一个数据类型时，不仅要完成词法分析中token的识别，还要再yacc中正确识别date格式。（这里其实有多种实现。）然后还要实现绑定这个类的各个操作，可能需要实现加减法，乘除法，从字符串来，到字符串去。

在后续测试过程中，再详细了解他实现的接口在哪一部分被使用。

添加vector向量类型也是按照此法进行操作。
