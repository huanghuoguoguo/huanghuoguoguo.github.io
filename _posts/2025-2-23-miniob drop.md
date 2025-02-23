---
layout: post
title: "miniob drop"
date:   2025-2-23
tags: [miniob，数据库]
comments: true
author: huanghuoguoguo
---

![赛题内容](https://huanghuoguoguo.github.io/images/1740118990050-959dd3aa-2064-41c0-8898-874e4ca2c2c6.png)

这里使用Clion来实现drop table功能，具体部署过程可以参考部署篇，建议先熟悉常用的git指令以及如何使用clion操作git，规范开发流程。

删表是建表的逆过程。 使用create建一张表t1之后，会创建元数据和相关的关联资源，数据文件（.text文件，后面会实现）、相关索引文件（.index文件）、元数据文件（.table）。所以drop table要实现的便是删除这些元数据和相关资源。

## 1. 环境准备

从main分支新建一个git 分支 ，命名为dev_2025_drop.

![新建分支](https://huanghuoguoguo.github.io/images/1739867290060-70aa8e23-f078-4db1-94f5-2575f9b383d1.png)



PS： 如果遇到下面的错误，是因为windows文件格式（CRLF）上传到linux（LF）导致的换行符错误

![换行符错误处理](https://huanghuoguoguo.github.io/images/1739867486207-7f58a651-925b-46fb-98a2-4520c01c46ac.png)

此时需要将下面几个文件的格式修改为 LF ：src/observer/sql/parser/gen_parser.sh、src/observer/sql/parser/lex_sql.l、src/observer/sql/parser/yacc_sql.y、build.sh。

修改完毕之后部署上传到远程服务器之后重新构建即可。

![更换换行符](https://huanghuoguoguo.github.io/images/1739867683751-181e9923-06b9-4e6c-9d0e-08bc58f1b2a4.png)        ![如果勾选了自动上传，这一步可以省略](https://huanghuoguoguo.github.io/images/1739867822965-c050ede9-77ac-4b42-87c0-04845beb7391.png)

## 2. drop table 实现准备



目前的miniob已经拥有了创建表的功能，以 `create table t1(id int , age int);` 语句为例，可以看到运行成功并输出了日志。

![创建表](https://huanghuoguoguo.github.io/images/1739868531472-0f05754c-e30e-4bb1-96d5-453f3db7d5fd.png)

现在我们要把t1删除，即 drop table t1; 我们要把创建的元数据和相关的关联资源删除，就需要找到这些资源的路径。因此我们需要参照create table的实现来**逆向**的实现drop功能。

建议先去调试一遍create table的过程，熟悉整个miniob的整体框架。

<details class="lake-collapse"><summary id="u5a9ef5da"><span class="ne-text">create table 源码分析</span></summary><p id="u7945606d" class="ne-p" style="margin: 0; padding: 0; min-height: 24px"><span class="ne-text">打开debug，输入一个建表sql语句，SqlTaskHandler::handle_event函数就会去处理这个request请求，获取这个事件之后，就会去执行sql语句：handle_sql函数</span></p><p id="u1ae8c506" class="ne-p" style="margin: 0; padding: 0; min-height: 24px; text-align: center"><img src="https://cdn.nlark.com/yuque/0/2024/png/38986152/1723710263102-94a2c79d-fb64-498e-9b4f-50f953d2a40e.png" width="1378.0179706601677" title="debug" crop="0,0,1,1" id="RSKQz" class="ne-image"></p><p id="ue1761457" class="ne-p" style="margin: 0; padding: 0; min-height: 24px"><span class="ne-text">根据handle_sql 函数逐个分析步骤：</span></p><p id="u3a27c3bb" class="ne-p" style="margin: 0; padding: 0; min-height: 24px; text-align: center"><img src="https://cdn.nlark.com/yuque/0/2024/png/38986152/1723710957670-957cc72a-cfa4-41eb-9915-378221872ecb.png" width="958.5585256161208" title="stage" crop="0,0,1,1" id="TNYhR" class="ne-image"></p></details>

 建表完成后，在linux终端可以看到创建表之后的文件：

![创建的文件](https://huanghuoguoguo.github.io/images/1739870105475-38458466-cf7f-455b-b097-41ad2a8085c3.png)



## 3. drop table 编写

由于miniob框架已经实现了`drop table`的部分内容，比如词法分析文件`lex_sql.l`中的`drop`关键字、`DropTableSqlNode`等，所以我们可以使用clion的DEBUG模式快速找到需要修改的地方。

![编译成功](https://huanghuoguoguo.github.io/images/1739881101358-37c5168e-933c-48cd-81a0-4c0ce3872ff1.png)

在`src/observer/net/sql_task_handler.cpp`中包含了整个miniob架构中的各个关键阶段的入口代码：

![img](https://huanghuoguoguo.github.io/images/1739880661428-78876413-7b7c-47b4-a75d-79a30e4ac3a4.png)

通过跳断点的方式快速找到在哪一阶段出现错误。

![img](https://huanghuoguoguo.github.io/images/1739881337853-1c5500fd-a9e6-46e9-93e8-455720d85394.jpeg)

分析可知`parse_stage_`阶段已经生成了`DropTableSqlNode`

![img](https://huanghuoguoguo.github.io/images/1739882110967-3d3b1ef3-b89f-4523-a960-19964283348b.png)

但是`resolve_stage_`阶段没有生成drop table的stmt。因此需要获取`drop_table_stmt .`

```cpp
// 部分代码
RC Stmt::create_stmt(Db *db, ParsedSqlNode &sql_node, Stmt *&stmt)
{
    stmt = nullptr;

    switch (sql_node.flag) {

        case SCF_CREATE_TABLE: {
            return CreateTableStmt::create(db, sql_node.create_table, stmt);
        }

        case SCF_DROP_TABLE: {
            return DropTableStmt::create(db, sql_node.drop_table, stmt);
        }
```

之后在`src/observer/sql/stmt`文件夹下创建`drop_table_stmt.cpp`和`drop_table_stmt.h`

仿照create table的实现，drop_table需要的参数只有table_name

```cpp
#include "sql/stmt/drop_table_stmt.h"
#include "event/sql_debug.h"

RC DropTableStmt::create(Db *db, const DropTableSqlNode &drop_table, Stmt *&stmt)
{
  stmt = new DropTableStmt(drop_table.relation_name);
  sql_debug("drop table statement: table name %s", drop_table.relation_name.c_str());
  return RC::SUCCESS;
}
#pragma once

#include <string>
#include <vector>

#include "sql/stmt/stmt.h"

class Db;

/**
 * @brief 表示删除表的语句
 * @ingroup Statement
 * @details 虽然解析成了stmt，但是与原始的SQL解析后的数据也差不多
 */
class DropTableStmt : public Stmt
{
public:
  DropTableStmt(
      const std::string &table_name)
      : table_name_(table_name)
  {}
  virtual ~DropTableStmt() = default;

  StmtType type() const override { return StmtType::DROP_TABLE; }

  const std::string                  &table_name() const { return table_name_; }


  static RC            create(Db *db, const DropTableSqlNode &drop_table, Stmt *&stmt);


private:
  std::string                  table_name_;
};
```

再次调试可以看到已经生成了drop table的stmt：
![img](https://huanghuoguoguo.github.io/images/1739882896780-897296e4-5fc0-4092-8233-93062053168d.png)



因为drop table只需要获取table name之后找到需要删除的表的相关资源路径，所以不需要生成逻辑计划和物理计划，可以跳过`optimize_stage_`

在`execute_stage_`阶段，我们已经拿到了需要的stmt，可以在这里直接进行文件的删除：
       在`src/observer/sql/executor/command_executor.cpp`中同样仿照create table，创建`DropTableExecutor`：

```cpp
// 仅展示部分代码
RC CommandExecutor::execute(SQLStageEvent *sql_event)
{
  switch (stmt->type()) {
    case StmtType::CREATE_TABLE: {
      CreateTableExecutor executor;
      rc = executor.execute(sql_event);
    } break;

    case StmtType::DROP_TABLE: {
      DropTableExecutor executor;
      rc = executor.execute(sql_event);
    } break;
```

之后创建`drop_table_executor.cpp`和`drop_table_executor.h`，并实现

```cpp
#pragma once

#include "common/rc.h"

class SQLStageEvent;

/**
 * @brief 删除表的执行器
 * @ingroup Executor
 */
class DropTableExecutor
{
public:
  DropTableExecutor()          = default;
  virtual ~DropTableExecutor() = default;

  RC execute(SQLStageEvent *sql_event);
};
#include "sql/executor/drop_table_executor.h"

#include "common/log/log.h"
#include "event/session_event.h"
#include "event/sql_event.h"
#include "session/session.h"
#include "sql/stmt/drop_table_stmt.h"
#include "storage/db/db.h"

RC DropTableExecutor::execute(SQLStageEvent *sql_event)
{
  Stmt    *stmt    = sql_event->stmt();
  Session *session = sql_event->session_event()->session();
  ASSERT(stmt->type() == StmtType::DROP_TABLE,
      "drop table executor can not run this command: %d",
      static_cast<int>(stmt->type()));

  DropTableStmt *drop_table_stmt = static_cast<DropTableStmt *>(stmt);

  const char *table_name = drop_table_stmt->table_name().c_str();
  RC rc = session->get_current_db()->drop_table(table_name);

  return rc;
}
```

其中session->get_current_db()->drop_table(table_name);中的drop_table方法需要在db中单独实现。：

```cpp
 /**
   * @brief 删除一个表
   * @param table_name 表名
 */
 RC drop_table(const char *table_name);
RC Db::drop_table(const char *table_name)
{
  // 检查一下表存不存在
  if (opened_tables_.count(table_name) == 0) {
    LOG_WARN("%s do not exist.", table_name);
    return RC::SCHEMA_TABLE_NOT_EXIST;
  }

  // 找到要删除的表
  Table *table = opened_tables_[table_name];
  // 从opened_tables_删除表
  opened_tables_.erase(table_name);
  delete table;

  // 获取表的元数据文件路径
  string table_meta_path = table_meta_file(path_.c_str(), table_name);

  // 获取表的实际数据文件路径
  string table_data_path = table_data_file(path_.c_str(), table_name);

  // 删除元数据文件
  if (std::remove(table_meta_path.c_str()) != 0) {
    // 如果删除失败，输出错误信息
    LOG_INFO("Error deleting metadata file for %s .",table_name);
    return RC::IOERR_UNREMOVE;
  }
  LOG_INFO("Metadata file: %s deleted successfully.",table_meta_path.c_str());

  // 删除数据文件
  if (std::remove(table_data_path.c_str()) != 0) {
    // 如果删除失败，输出错误信息
    LOG_INFO("Error deleting data file for %s .",table_name);
    return RC::IOERR_UNREMOVE;
  }
  LOG_INFO("Metadata file: %s deleted successfully.",table_data_path.c_str());

  return RC::SUCCESS;
}
```

其中`db.cpp`中有一个自定义的状态码`IOERR_UNREMOVE`，需要在 `src/observer/common/rc.h`中单独加上。

```cpp
#define DEFINE_RCS                       \
  DEFINE_RC(SUCCESS)                     \
  DEFINE_RC(IOERR_UNREMOVE)              \
```



如上便实现了简单的drop table的功能。![img](https://huanghuoguoguo.github.io/images/1739883784946-2e26ce12-b533-4758-a0a0-a4d48def9267.png)

目前已经可以通过官方的提测，但是还可以进一步的优化，比如删除表的同时删除索引、如果存在text类型的数据还需删除text文件等等。感兴趣的话可以尝试一下。
