---
layout: post
title: "miniob server简析"
date:   2025-2-22
tags: [miniob，数据库]
comments: true
author: huanghuoguoguo
---

主要关注Server即可，deps，Client的代码都不需要改动。同时本篇只关注行式存储，不关注列式存储，更关注单线程模型，不关注多线程模型。

以下是我认为比较重要的板块，根据比赛编码的重要程度做了内容篇幅上的划分，但是仍然可以以比较少的文本说明板块的作用。通过阅读本篇，可以快速知道MiniOB的组成部分，以及或许对解题有些许帮助。

# Net&Event&Session

Server从服务启动到监听连接是可以不用关注的，关键代码其会根据配置文件和启动方式的不同启动不同的连接器，有单线程的Cli模式，有多线程的net模式。在我们开发赛题代码的过程中也主要测试单线程的模式，但是了解不同的连接方式有利于开拓视野。

## Net

客户端通过网络发送一个请求到服务端，服务端在接收到消息后会创建一个消息包，并创建对应的SessionEvent。然后调用add_event把SessionEvent添加到SessionStage里（参考`net/server.cpp`中`session_stage_->add_event(sev);`），再放到对应的事件队列中。SessionStage以及后续处理事件的几个Stage，都在SQLThreads线程池中。

SessionStage处理SessionEvent后，会创建一个SQLStageEvent传递给后面的Stage。后续的Stage都是处理这个SQLStageEvent的事件。如下图所示，事件经过一个流转，处理完成后返回结果给客户端。

![处理顺序](https://huanghuoguoguo.github.io/images/1740029688510-d81e3274-fea2-4147-b7fe-20be57f16b20.png)

## Session

表示一次连接的上下文。可以理解它维护了我们此次连接的环境信息，sql字符串，次数等等。

```cpp
/**
 * @brief 表示一个SQL请求
 *
 */
class SessionEvent
{
public:
  SessionEvent(Communicator *client);
  virtual ~SessionEvent();

  Communicator *get_communicator() const;
  Session      *session() const;

  void set_query(const string &query) { query_ = query; }

  const string &query() const { return query_; }
  SqlResult    *sql_result() { return &sql_result_; }
  SqlDebug     &sql_debug() { return sql_debug_; }

private:
  Communicator *communicator_ = nullptr;  ///< 与客户端通讯的对象
  SqlResult     sql_result_;              ///< SQL执行结果
  SqlDebug      sql_debug_;               ///< SQL调试信息
  string        query_;                   ///< SQL语句
};
```

## Event

MiniOB有很多处理阶段，如词法解析、语法解析、Resolver、优化器等。MiniOB使用了SEDA的框架，像Resolver、优化器等在SEDA中都是一个个的Stage，各个Stage之间通过事件来传递数据。MiniOB的多线程能力是基于SEDA来做的，SEDA本身就是支持线程池的。在这里我们不需要具体去理解SEDA是干什么的，只需要去知道MiniOB对一个连接事件的发生，肯定是做了某种抽象和封装的，对每个阶段划分了生命周期，认为其是一个实体，有输入和输出，并且事件处于这几个阶段中的一个，代表数据从上流至下，然后又流转出去。我们将这部分淡化，只需要知道这是辅助控制sql执行并且返回结果的就好了。

![处理流程](https://huanghuoguoguo.github.io/images/1740029502071-0cf37d29-62f4-4b1c-9abc-200dc6889145.png)

下图所示是一个简单的SEDA框架图，能够很好的帮助理解MiniOB中的每个Stage和event，以及线程池之间的关系。线程池可以有多个，每个线程池可以包含多个Stage，一个Stage会绑定到某一个线程池里面。每个线程池可以设置自己的线程的个数、事件队列的大小，线程池中的多个Stage之间是通过事件通讯的。虽然示例图中写的都是StageEvent，但也可以是不同的名字。另外，不同的线程池之间的Stage也可以通过事件通讯，并且每一个线程池里面的Stage可以是不同的。

![线程池处理流程图](https://huanghuoguoguo.github.io/images/1740029516155-fa491fe2-9877-4525-8dc5-00929f758c32.png)

SEDA框架有一个好处是可以将Stage进行分类，比如把处理SQL的分作一类，把IO处理的分作为一类，并把不同的分类分配到不同的线程池。这样在处理任务时不容易受到其他干扰，并且也能够根据真实的业务场景去调整每个线程池的大小。

接下来看一个简单的Stage模型。一个Stage对应一个类型的事件，事件是放在线程池事件队列中的。线程池事件指当事件队列有事件后，就将其交给对应的Stage来处理。


![队列模型](https://huanghuoguoguo.github.io/images/1740029531402-22955181-41d9-40be-8764-ddcd8991cb35.png)

具体到代码中，我们只需要关注一次事件在内部是如何流转的，他的输入是用户输入的字符串，输出是本次执行的结果。我们不关注太多实现细节，了解MiniOB对其做的抽象和代表的含义即可。感兴趣的同学参考官网和源码做进一步的了解。

## Buffer

在I/O操作中，缓冲区是一个普遍存在的概念。例如，在CPU与内存之间的交互过程中，高速缓存充当了缓冲区的角色；而在内存与硬盘之间，则是pagecache作为缓冲区。此外，在数据传输过程中，队列也可以作为一种缓冲机制。实际上，在大多数管道形式的数据流架构中，引入缓冲区往往能够带来显著的性能提升。具体来说，当用户指令被处理并生成结果后，该结果需要通过某种方式传递给用户。在同一台机器上，这通常涉及到内存间的复制过程，即将数据从一个程序的内存空间复制到另一个程序的内存空间。而在分布式环境中，数据则需被复制至网络接口前的一个特定位置。如果主程序能够在完成其核心逻辑后，无需直接管理后续的数据流向，而是将数据存储在一个固定的位置，之后由专门设计的异步程序来负责取出这些数据进行进一步处理，这样可以极大地简化主程序的设计，并提高整体系统的效率。这种模式在软件和硬件设计领域有着广泛的应用实例，并已成为一种重要的设计理念，如消息队列模型等。

## Communicator

负责持有输入和输出。持有session，bufferwriter，fd文件描述符。

## Threadpool

池化的思想在很多地方都会用到，资源的复用，环形缓冲区，缓存，我们都可以这么理解。

![poll](https://huanghuoguoguo.github.io/images/1740032736005-0e7d22da-ed18-4eaa-ac82-7a28f612eea3.png)

在server.cpp文件中这里有一个以后非常感兴趣的方法poll，感兴趣的同学可以具体看看net_server是怎么接受事件然后用线程处理的。这里不是我们学习的重点。

## Handler

持有communicator，控制sql语句执行的流转，跟我们之前讨论的stage流程差不多。

# sql

数据库领域经过长期的发展已经形成了比较稳定的工程结构，本节主要通过介绍MySQL和OceanBase的SQL层架构来帮助大家理解整个SQL内核层是如何组织的。

![从解析到执行流程图](https://huanghuoguoguo.github.io/images/1740035318851-f156e8c8-4525-47df-bf15-e1d02ef8b5d7.png)

从图中可以看出MySQL在SQL层的处理模块分别是查询缓存、分析器、优化器和执行器。在OceanBase数据库的架构解析图中列出了较为详细的处理模块，并在图中用不同的颜色框，与MySQL的各模块一一对应。在接下几节中会按照右边图示，讲解一条SQL被发送给Server后从解析到执行的全过程。

无论是经常使用数据库做查询，还是专门做数据库内核的同学，对一条SQL语句不同结构的执行顺序应该都有所了解。

```sql
SELECT <字段名> (9)
FROM <表名> (1)
JOIN <表名> (2)
ON <连接条件>(2) 
WHERE <筛选条件>(3) 
GROUP BY <字段名> (4)
HAVING <筛选条件> (5)
ORDER BY <字段名>(7) 
LIMIT <限制行数>(8);

# 此处不包含 subquery
```

如上所示SQL，其中标注出了执行序号，可以看到一条SQL语句的书写顺序与它的执行顺序通常都是不一样的，可能有些数据库的特定实现不一定按照这个顺序，但总体上都是比较类似的。感兴趣的同学可以查阅相关资料，了解为什么这样一条SQL的执行顺序是像示例中标注的这样，而不是其他顺序。也可以尝试打乱顺序，分析这样会对SQL执行造成什么样的影响。

Server端是怎么一步步的去解析这条SQL的呢？实际上，SQL是为了方便让使用者去向数据库Server端表达信息的一种描述性的语言，具体Server端怎么样处理，是在数据库内核层面去实现的。

## Parser词法分析和语法分析

当一条SQL请求到达Server端后，首先经过的是Parser模块。Parser模块主要作用是根据定义的语法规则判断一条SQL语句的格式是否符合对应的语法结构，这个语法结构无论是在MySQL还是OceanBase中，都是使用Yacc和Flex工具自动生成的。需要重点理解Parser模块是如何将一条用户写的SQL请求转换成可以在数据库内核中所使用的数据结构。

如下图所示，SQL语句`SELECTc1+c2FROMt1WHEREexists`再接着一个子查询，然后子查询是由unionall连接的另外两个子查询。Parser模块最终解析出来的是一个逻辑结构图，就像示例图中这样一个树状结构。

![示例语法树图](https://huanghuoguoguo.github.io/images/1740033321572-daa633a7-1e89-4c02-ae4d-43b4dc3ae728.png)

接下来介绍一下具体是如何实现的，无论是SELECT、FROM还是WHERE，都会有自己所附带的一些成分。

- selectlist是一个表达式操作，即`c1+c2`。再递归解析，它的根节点是`+`，两个子节点分别是参与运算的两个常量c1和c2。
- fromlist的参数其实是一个relation，也就是一个表名，即t1。
- where代表的是condition条件，这里的condition操作符是exists，exists后面是一个subquery。这个subquery可以递归地向下去分解，它是由unionall所连接起来的两个subquery。同理这两个subquery也可以再递归地向下展开。

一条SQL语句，无论写得多么复杂，本质上就是一层一层嵌套的树状结构。Parser模块这一个部分主要做的就是根据用户所写的语法规则正确的识别，并将一条SQL语句转化为一个语法树的结构。但一条符合语法树规则的SQL不一定是一条“合格”的SQL，数据库中还存在着许多约束，一条SQL还必须满足语义的约束，许多语法的约束以及虚视图的展开都是在Resolver模块中完成的。



## DataType&Value

在MiniOB中，sql字符串要绑定为内部使用的数据结构，除了按规则转变，还需要定义具体的数据类型、字段类型。

这部分在common的type中表示。

![common/type目录](https://huanghuoguoguo.github.io/images/1740035954014-a3fd9640-19c0-417f-8c03-4c54e69add69.png)

### DataType

目前已经定义的有：int，float，char，他们都继承了data_type基类，并且实现了部分方法。尽管目前还没有接触到他们怎么被使用，但是理解数据的最小粒度的表示还是有益于我们理解整个程序的运转。同时要强调的是，这不仅仅是MiniOB的特殊化处理，大部分处理数据的应用都会自己实现一套处理数据的方式，而且也是用这种面向对象的方式，将基本数据类型包装成类，这种做法会频繁出现在各个项目里。

```cpp
/**
 * @brief 定义了数据类型相关的操作，比如比较运算、算术运算等
 * @defgroup DataType
 * @details 数据类型定义的算术运算中，比如 add、subtract 等，将按照当前数据类型设置最终结果值的类型。
 * 参与运算的参数类型不一定相同，不同的类型进行运算是否能够支持需要参考各个类型的实现。
 */
class DataType
{
public:
  explicit DataType(AttrType attr_type) : attr_type_(attr_type) {}

  virtual ~DataType() = default;

  inline static DataType *type_instance(AttrType attr_type)
  {
    return type_instances_.at(static_cast<int>(attr_type)).get();
  }

  inline AttrType get_attr_type() const { return attr_type_; }

  /**
   * @return
   *  -1 表示 left < right
   *  0 表示 left = right
   *  1 表示 left > right
   *  INT32_MAX 表示未实现的比较
   */
  virtual int compare(const Value &left, const Value &right) const { return INT32_MAX; }

  /**
   * @brief 计算 left + right，并将结果保存到 result 中
   */
  virtual RC add(const Value &left, const Value &right, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 计算 left - right，并将结果保存到 result 中
   */
  virtual RC subtract(const Value &left, const Value &right, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 计算 left * right，并将结果保存到 result 中
   */
  virtual RC multiply(const Value &left, const Value &right, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 计算 left / right，并将结果保存到 result 中
   */
  virtual RC divide(const Value &left, const Value &right, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 计算 -val，并将结果保存到 result 中
   */
  virtual RC negative(const Value &val, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 将 val 转换为 type 类型，并将结果保存到 result 中
   */
  virtual RC cast_to(const Value &val, AttrType type, Value &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 将 val 转换为 string，并将结果保存到 result 中
   */
  virtual RC to_string(const Value &val, string &result) const { return RC::UNSUPPORTED; }

  /**
   * @brief 计算从 type 到 attr_type 的隐式转换的 cost，如果无法转换，返回 INT32_MAX
   */
  virtual int cast_cost(AttrType type)
  {
    if (type == attr_type_) {
      return 0;
    }
    return INT32_MAX;
  }

  virtual RC set_value_from_str(Value &val, const string &data) const { return RC::UNSUPPORTED; }

protected:
  AttrType attr_type_;

  static array<unique_ptr<DataType>, static_cast<int>(AttrType::MAXTYPE)> type_instances_;
};
```

当我们要新增一个字段类型的时候，就需要仿照其他的字段类型，实现对应的方法，在类型池中注册，才能被使用。具体怎么被使用，当我们实现操作符的时候可以看到。这里先不去了解，总之，它身上定义的方法决定了一个字段类型怎么被存取，怎么做比较。

### Value

除了字段类型，还需要知道数据类型。value.h定义了一个最小粒度的数据在内存中是怎么存储的。对于实际存储在内存中的数据都是这种形式维护的，在存取的时候通过AttrType调用对应的方法进行操作。

```cpp
AttrType attr_type_ = AttrType::UNDEFINED;
  int      length_    = 0;

  union Val
  {
    int32_t int_value_;
    float   float_value_;
    bool    bool_value_;
    char   *pointer_value_;
  } value_ = {.int_value_ = 0};
```

## Expr

### Expression

表达式。在MiniOB中，表达式是一个重要的载体。先列出目前已经实现的表达式类型（可以自己添加实现）：

```cpp
enum class ExprType
{
    NONE,
    STAR,///<星号，表示所有字段
    UNBOUND_FIELD,///<未绑定的字段，需要在resolver阶段解析为FieldExpr
    UNBOUND_AGGREGATION,///<未绑定的聚合函数，需要在resolver阶段解析为AggregateExpr
    
    FIELD,///<字段。在实际执行时，根据行数据内容提取对应字段的值
    VALUE,///<常量值
    CAST,///<需要做类型转换的表达式
    COMPARISON,///<需要做比较的表达式
    CONJUNCTION,///<多个表达式使用同一种关系(AND或OR)来联结
    ARITHMETIC,///<算术运算
    AGGREGATION,///<聚合运算
};
```

在SQL的元素中，任何需要得出值的元素都可以使用表达式来描述。

比如获取某个字段的值、比较运算、类型转换。当然还有一些当前没有实现的表达式，比如算术运算。

通常表达式的值，是在真实的算子运算过程中，拿到具体的tuple后才能计算出来真实的值。但是有些表达式可能就表示某一个固定的值，比如ValueExpr。

比如`SELECT*,id+1FROMtestWHEREid>1`这个sql语句，在后续处理过程中，*会被包装成StarExpr，id+1会被绑定ArithmeticExpr，为test会绑定具体的Table类，id会被包装成FieldExpr，1会被包装成ValueExpr。基类会有以下接口：



```cpp
// 判断两个表达式是否相等
virtual bool equal(const Expression &other) const { return false; }

// 根据具体的 tuple，来计算当前表达式的值。tuple 可能是一个具体某个表的行数据
virtual RC get_value(const Tuple &tuple, Value &value) const = 0;

// 在没有实际运行的情况下，也就是无法获取 tuple 的情况下，尝试获取表达式的值
// 有些表达式的值是固定的，比如 ValueExpr，这种情况下可以直接获取值
virtual RC try_get_value(Value &value) const { return RC::UNIMPLEMENTED; }

// 可以根据表达式类型来转换为具体的子类
virtual ExprType type() const = 0;

// 一个表达式运算出结果后，只有一个值
virtual AttrType value_type() const = 0;

// 表达式值的长度
virtual int value_length() const { return -1; }

// 表达式的名字，比如是字段名称，或者用户在执行 SQL 语句时输入的内容
virtual const char* name() const { return name_.c_str(); }
virtual void set_name(string name) { name_ = name; }

// 表达式在下层算子返回的 chunk 中的位置
virtual int pos() const { return pos_; }
virtual void set_pos(int pos) { pos_ = pos; }
```

具体的子类会有不同的行为，比如StarExpr最终会被解析绑定为FieldExpr，或者ArithmeticExpr最终调用get_value会得到当前tuple的值。

具体在MiniOB中怎么被使用，我们要不要去做功能上的增强，都会在后续解决问题的过程当中体现。

### Tuple

我们可以认为，在MiniOB中Tuple是一行逻辑上的数据，它有列，每个列有元数据，你给它列索引，或者列名，它返回具体的值。它的子类有:

- RowTuple，一行数据的元组，直接就是获取表中的一条记录，可以直接理解为原始数据表中的一行。
- ProjectTuple，映射，有的时候可能是id+1这样的输出列，他不是原始数据表的列，需要对其做一层包装。
- ValueListTuple，一些常量值组成的Tuple。
- JoinedTuple，将两个tuple合并为一个tuple。

在火山模型中，每一层的算子可以简化的不考虑下一层传递上来的Tuple是什么类型，只面向函数接口编程。

Tuple实现以下几个接口：

```cpp
// 获取元组中的 Cell 的个数
virtual int cell_num() const = 0;

// 获取指定位置的 Cell
virtual RC cell_at(int index, Value &cell) const = 0;

// 获取指定位置的元组单元格规格
virtual RC spec_at(int index, TupleCellSpec &spec) const = 0;

// 根据 cell 的描述，获取 cell 的值
virtual RC find_cell(const TupleCellSpec &spec, Value &cell) const = 0;

// 比较两个元组
virtual RC compare(const Tuple &other, int &result) const;
```

和record区分开来，tuple是逻辑上的一行数据，可能经过了改造，record持有一个rowTuple，可以认为rowTuple是数据表上的一行真实原始数据。

### Tuple_cell

Tuple中的一列。有列名，表名，字段名。可以根据传递一个描述对象，获取到指定的值。

## Statement

Resolver模块主要作用是对Parser模块所生成的符合语法规则的树状结构进行进一步的约束检查，还可能会提取表达式的属性。为便于大家理解接下来介绍几个示例。

- 元数据和字段的绑定

- 像上面我们提到的，将sql字面量进行绑定，table名进行检查并绑定为内部使用的数据结构，*号绑定为具体的字段数据结构，groupby函数进行函数对象的绑定。不存在的表，不存在的字段都会直接报错。

- 关系或属性的检查

- 关系或属性的检查主要是看表名、列名和别名是否有歧义、是否合法。比如当查询某张表中的一些列属性，FROM子句出现的关系必须存在。也就是说当一张表都不存在，那查询肯定是没有意义的，或者当查询的属性没有出现在所查询的表中，当然也不满足数据库约束的要求。

- 类型的检查

- LIKE操作符：要求匹配的属性必须是一个字符串，或可以转化成一个字符串结构。

- 类型推演

- 类型推演主要是提取表达式的属性用于后续分析，比如共享一些表达式，或者优化一些表达式计算之类的，对之后查询计划的优化有很大的作用。

为后续创建逻辑计划和物理计划做信息收集和检查。当我们要实现新的语句的时候，比如create-select，就需要新实现一个statement。



## Operator&Optimizer

经过前几节的介绍，了解了一条SQL请求在Parser模块主要关注的是语法树逻辑结构，在Resolver模块主要关注的是符合语义要求的树形的结构。在OceanBase和MiniOB中，数据结构在Resolver层实际上是一个Statement，这也是OceanBase和MiniOB后续进行Transformer和optimizer改写的基础。

![关键stage](https://huanghuoguoguo.github.io/images/1740107471763-3577af6d-a8a4-4984-a3e2-5fcc21435410.png)

### optimize_stage

![优化代码](https://huanghuoguoguo.github.io/images/1740107836484-32fd27b7-6236-489d-9512-4993e3307b42.png)

#### rewrite

![部分重写代码](https://huanghuoguoguo.github.io/images/1740108000913-cc8664b7-13c7-4618-98b8-e54734adb959.png)

在重写的具体方法中，他是以递归的形式，扫描所有的算子是否符合条件的。这里不详细描述太多，有机会再开一个篇幅讲讲大体的逻辑流程，初学时不必考虑这个。

#### optimize

![空的optimize方法](https://huanghuoguoguo.github.io/images/1740108180560-958aac62-bd3a-4737-9d50-6c05c4631e63.png)

优化阶段在MiniOB中什么也没有做。

### 火山模型

不过在Transformer和optimizer层，重点需要关注的是火山模型的结构，火山模型详细介绍请参见Executor。这里介绍一个示例来帮助大家理解，示例中SQL的语义是：挑选出某场电影的名字和卖出的票数，并且它的票数需要大于50张。这里假设在七点钟，只有一场电影在播放，并且卖出的票数超过了100张。即当执行这条SQL的时候，会查出这场电影和卖出的票数。

```sql
SELECT movie.name,play.ticket
FROM movie
JOIN play
ON movie.time = play.time
WHERE play.ticket>50;
```

下图所示是这条SQL简单的执行计划。首先分别对两张表进行全部字段的遍历，遍历所有字段后做表连接操作，操作的条件为`movie.time=play.time`，即时间一致。连接之后生成一张新表，再去根据条件`play.ticker>50`去过滤，最后将需要查询的`play.ticker`和`movie.name`给投影出来。

![示例逻辑图](https://huanghuoguoguo.github.io/images/1740057655971-b4595b6f-36fc-4734-bd6b-f34e51b35fb2.png)

接下来看一下它是如何优化的。

投影（Projcet）操作实际上只需要投影出特定的列，包括在做Join条件时也是要需要一个时间的字段，所以第一个优化是减少遍历属性，可以将上层的投影给去掉，然后将Scan的操作只遍历特定的属性，两张表都是这样，做完这个优化后，就减少了一个投影操作。![优化过程图](https://huanghuoguoguo.github.io/images/1740057821078-a9724679-d02d-42d7-89bf-8dc780562a09.png)

第二个优化是因为最终符合条件的只需要卖出的**票数大于50**张的场次，所以在遍历play表的时候，不需要将所有的电影及对应票数都筛选出来，只需要筛选出票数大于50张的排片。

经过优化之后它由四层的结构变成了两层，只需遍历出需要的字段，然后做一个Join操作就可以了。不仅操作路径变短了，而且表的连接项也变得更少了，相比之前查询计划更优。

大部分成熟的数据库都会实现相关的计划优化模块，在OceanBase的数据库中，针对于查询计划也实现了一个比较完整的的优化模型，OceanBase的优化模型主要包括查询改写、代价模型和统计信息三个模块。而在MiniOB中，就有一些赛题需要实现1=1逻辑去除，condition下推，当遇到相关赛题时可以去查看更多资料。

## Executer

Executor模块中最经典的模型是VolcanoModel（火山模型），它是一种基于行的流式迭代模型（Row-BasedStreamingIteratorModel），目前主流的关系数据库中都采用了这种模型，例如Oracle、SQLServer、MySQL等。

在火山模型中，所有的代数运算符（operator）都被看成是一个迭代器，它们都提供一组简单的接口：open()—next()—close()，查询计划树由一个个这样的关系运算符组成，每一次的next()调用，运算符就返回一行（Row），每一个运算符的next()都有自己的流控逻辑，数据通过运算符自上而下的next()嵌套调用而被动的进行拉取。

![火山模型示例](https://huanghuoguoguo.github.io/images/1740057858903-32657ee9-9b40-4cd8-befd-2bb8911ced5f.png)

火山模型中每一个**运算符都将下层的输入看成是一张表**，next()接口的一次调用就获取表中的一行数据，这样设计的优点是：每个运算符之间的代数计算是相互独立的，并且运算符可以伴随查询关系的变化出现在查询计划树的任意位置，这使得运算符的算法实现变得简单并且富有拓展性。

这种设计也会存在一些问题，如果没有一些阻塞性的操作，整个火山模型只需要很少的内存就能运作起来，每次只需要迭代一个tuple行。但有一些Operator（如sort、group），它是阻塞性的操作，要拿到所有的tuple之后，才能进行进行运算，这种操作符实际上是破坏了火山模型整体的流水性的运算。

另外一方面当处理的数据量增大时，也会有明显缺陷。因为每次只迭代一行，所以要向下调用很多层的next()函数，它导致了大量的虚函数开销，非常消耗CPU资源。

这个问题也是因为一些历史原因，火山模型最早于1990年GoetzGraefe在Volcano,anExtensibleandParallelQueryEvaluationSystem这篇论文中提出的，在90年代早期，计算机的内存资源十分昂贵，相对于CPU的执行效率，IO的效率要差得多。因此当时火山模型考虑的是将更多的内存资源用于IO的缓存设计，而没有考虑去优化这种结构导致的CPU方面执行效率的低下。从当时的条件来看，在硬件上它是一个非常合理的权衡。

经过多年的研究和发展，无论学术还是工业界都在火山模型的基础上不断改进，下面介绍几个示例：

- RowSet迭代

- 如下图所示，每次返回的不是一个tuple，而是一个RowSet。这种RowSet的迭代，它每一次的数据流传递不再是单行的模式，而是做单个tuple组成的集合。更多的运算就会停留在这个next()操作的内部，而不是在函数调用之间频繁的切换，可以减少next()的调用次数。同时这个局部的操作也有返回一个tuple，变成了一个局部的循环操作。这种循环操作实际上是可以用现代的一些编译技术或CPU动态指定预测技术来进行优化的，也能够提升我们的查询效率。

![火山模型](https://huanghuoguoguo.github.io/images/1740057859040-c8c4c74d-3008-43f4-81ae-74c18da17111.png)

以Project算子为例，这个算子从子set当中获取指定的一行。

```cpp
// 从 children[0] 中获取下一行。
RC ProjectPhysicalOperator::next() {
    if (children_.empty()) {
        return RC::RECORD_EOF;
    }
    return children_[0]->next();
}

// 返回当前选中的行。
Tuple* ProjectPhysicalOperator::current_tuple() {
    tuple_.set_tuple(children_[0]->current_tuple());
    return &tuple_;
}
```

- 操作符融合

- 如下图所示，在做TABLESCAN的时候，实际上做了一个过滤，过滤掉了`ss_item_sk=1000`的操作。可以看到无论是第几步都有Filter操作，而实际上是把Filter的操作放到了投影和Scan里面，这样可以减少一层的调用。比如说这里的Filter下推到Scan里面去过滤掉，这在前面介绍的查询计划的优化中也有类似的操作。

![OceanBase输出结构图](https://huanghuoguoguo.github.io/images/1740057859049-a4daf100-ed7c-42d2-a3c8-3fb4ad20baed.png)

- 拉取模型和推送模型

- 火山模型是一种被动的数据读取方式，它由上层的算子来驱动，当下层算子接受到上层算子的调用请求后，会返回符合条件的tuple。但更方便的方式，应该是由下层算子主动将数据推送给上层算子。

![火山模型展示图](https://huanghuoguoguo.github.io/images/1740057859010-ffb17404-36a5-44cc-b0d6-aa61532d1572.png)

为帮助大家理解拉取模型和推送模型的差异，接下来介绍一个示例。

下图中所示SQL，语义是从store_sales中挑选符合条件的商品，并做聚合去计数。下图左边所示是对应的火山模型。挑选出符合条件的tuple，然后返回给上层Aggr算子，再进行count操作去计数。

![火山模型与简单代码示例](https://huanghuoguoguo.github.io/images/1740057859057-de50bbdd-3a89-4d0d-89a5-b9b744303e60.png)

接下来分别来看一下上拉模型和下推模型的代码结构区别。

- 上拉引擎的代码结构

- 左边是经典的火山模型的一个伪代码，投影操作的代码这里没有列举出来。上拉模型是由上层的算子驱动，即从上层的AggregationOp去驱动，每次开始时，就会调用FilterOp的部分。FilterOp遇到符合条件的时候，会结束自己的调用，然后将这条信息传回给上一层。当row不等于null时，就会将计数加一，这是外层AggregationOp的调用。

- 下推引擎的代码结构

- 推送模型的数据流动是从下层开始的一个Scan操作，也就是从它的FilterOp开始。即首先遍历他自己Table，然后找到满足的行，推送给AggregationOp的部分，直接进行计数加一。可以看到下推引擎在代码的层次上相对上拉引擎简洁了许多，能够减少一些CPU资源的消耗。

那么在做MiniOB的赛题中，会涉及到非常多的算子编写的工作。同时建议在做一个赛题的时候，先有思路，再做评估，再去看相关代码，**是否已经有现有的代码做了相关工作了，最好不要重复造轮子**。

# Storage

首先回顾一下MiniOB的框架，在MiniOB概述章节已经简单的介绍过，本节重点介绍执行器（Executor）访问的**存储引擎**。

![数据库结构](https://huanghuoguoguo.github.io/images/1740059105759-7a558358-15e8-44f9-bf45-78f657da6fb7.png)

存储引擎控制整个数据、记录是如何在文件和磁盘中存储，以及如何跟内部SQL模块之间进行交互。存储引擎中有三个关键模块：

- RecordManager：组织记录一行数据在文件中如何存放。
- BufferPool：文件跟内存交互的关键组件。
- B+Tree：索引结构。

![存储目录图](https://huanghuoguoguo.github.io/images/1740115037108-d9807b6f-df91-403b-a573-bd0db30ed40c.png)

## MiniOB文件管理

首先介绍MiniOB中文件是怎么存放，文件需要管理一些基础对象，如数据结构、表、索引。数据库在MiniOB这里体现就是一个文件夹，如下图所示，最上面就是一个目录，MiniOB启动后会默认创建一个sys数据库，所有的操作都默认在sys中。

![创建的文件](https://huanghuoguoguo.github.io/images/1740059105673-15007d02-2c14-49a3-801e-657f53e7b944.png)

一个数据库下会有多张表。上图示例中只有三张表，接下来以test1表为例介绍一下表里都存放什么内容。

- test1.table：元数据文件，这里面存放了一些元数据。如：表名、数据的索引、字段类型、类型长度等。
- test1.data：数据文件，真正记录存放的文件。
- test1-i_name.index：索引文件，索引文件有很多个，这里只展示一个示例。
- 可选，如果我们要存储一些额外的数据，或者超出页面长度的字段，可能还需要别的文件来存储。

## MiniOBBufferPool模块介绍

BufferPool在传统数据库里是非常重要的基础组件。

首先来了解一下为什么要有一个BufferPool，数据库的数据是存放在磁盘里的，但不能直接从磁盘中读取数据，而是需要先把磁盘的数据读取到内存中，再在CPU做一些运算之后，展示给前端用户。写入也是一样的，一般都会先写入到内存，再把内存中的数据写入到磁盘。这种做法也是一个很常见的缓存机制。

![页面管理](https://huanghuoguoguo.github.io/images/1740059105721-26c8315e-9ab1-4a00-a6b9-df61d0584bba.png)

接着来看BufferPool在MiniOB中是如何组织的。如上图所示，左边是内存，把内存拆分成不同的帧（frame）。假如内存中有四个frame，对应了右边的多个文件，每个文件按照每页来划分，每个页的大小都是固定的，每个页读取时是以页为单位跟内存中的一个frame相对应。

BufferPool在MiniOB里面组织的时候，一个DiskBufferPool对象对应一个物理文件。所有的DiskBufferPool都使用一个内存页帧管理组件BPFrameManager，他是公用的。

再来看下读取文件时，怎么跟内存去做交互的。如上图所示，frame1关联了磁盘中一个文件的页面，frame2关联了另一个页面，frame3是空闲页面，没有关联任何磁盘文件，frame4也关联了一个页面。

比如现在要去读取file3的Page3页面，首先需要从BPFrameManager里面去找一个空闲的frame，很明显，就是frame3，然后再把frame3跟它关联起来，把Page3的数据读取到frame3里。现在内存中的所有frame都对应了物理页面。

如果再去读取一个页面，如Page5，这时候已经找不到内存了，通常有两种情况：

- 内存还有空闲空间，可以再申请一个frame，跟Page5关联起来。
- 内存没有空闲空间，还要再去读Page4，已经没有办法去申请新的内存了。此时就需要从现有的frame中淘汰一个页面，比如把frame1淘汰掉了，然后把frame1跟Page4关联起来，再把Page4的数据读取到frame1里面。淘汰机制也是有一些淘汰条件和算法的，可以先做简单的了解，暂时先不深入讨论细节。

![page存储](https://huanghuoguoguo.github.io/images/1740059105740-781476b2-9e47-478b-8e48-004e1ffa2f5f.png)

再来看一下，一个物理的文件上面都有哪些组织结构，如上图所示。

- 文件上的第一页称为页头或文件头。文件头是一个特殊的页面，这个页面上会存放一个页号，这个页号肯定都是零号页，即pagenum是0。
- pagecount表示当前的文件一共有多少个页面。
- allocatedpages表示已经分配了多少个页面。如图所示标灰的是已经分配的三个页面。
- Bitmap表示每一个bit位当前对应的页面的分配状态，1已分配页面，0空闲页面。

当前这一种组织结构是有一个缺陷的，整个文件能够支持的页面的个数受页面大小的限制，也就是说能够申请的页面的个数受页面大小的限制的。有兴趣的，可以思考一下怎么能实现一个无限大或支持更大页面的算法。

接下来介绍一下普通页面（除PageHeader外），普通页面对BufferPool来说，第一个字段是用四字节的int来表示，就是pagenum。接下来是数据，这个数据是由使用BufferPool的一些模块去控制。比如RecordManage或B+Tree，他们会定义自己的结构，但第一个字段都是pagenum，业务模块使用都是pagedata去做组织。

## MiniOB记录管理

记录管理模块（RecordManager）主要负责组织记录在磁盘上的存放，以及处理记录的新增与删除。需要尽可能高效的利用磁盘空间，尽量减少空洞，支持高效的查找和新增操作。

MiniOB的RecordManager做了简化，有一些假设，记录通常都是比较短的，加上页表头，不会超出一个页面的大小。另外记录都是固定长度的，这个简化让学习MiniOB变得更简单一点。

![page示例](https://huanghuoguoguo.github.io/images/1740059105721-bacf981c-b6bb-49d8-9648-bd05360d024e.png)

上面的图片展示了MiniOB的RecordManager是怎么实现的，以及Record在文件中是如何组织的。

RecordManage是在BufferPool的基础上实现的，比如page0是BufferPool里面使用的元数据，RecordManage利用了其他的一些页面。每个页面有一个头信息PageHeader，一个Bitmap，Bitmap为0表示最近的记录是不是已经有有效数据；1表示有有效数据。PageHeader中记录了当前页面一共有多少记录、最多可以容纳多少记录、每个记录的实际长度与对齐后的长度等信息。



## DB

一个DB实例负责管理一批表。

当前DB的存储模式很简单，一个DB对应一个目录，所有的表和数据都放置在这个目录下。

启动时，从指定的目录下加载所有的表和元数据。

一个DB实例会有一个BufferPoolManager，用来管理所有的数据页，以及一个LogHandler，用来管理所有的日志。

这样也就约束了事务不能跨DB。bufferpool的内存管理控制也不能跨越Db。

也可以使用MiniOB非常容易模拟分布式事务，创建两个数据库，然后写一个分布式事务管理器。

数据库对象没有做完整的并发控制。比如在查找某张表的同时删除这个表，会引起访问冲突。这个控制是由使用者来控制的。如果要完整的实现并发控制，需要实现表锁或类似的机制。

在我们做赛题的时候，一般不需要对这里做什么改动，同时默认是当前数据库且只有一个数据库。

```cpp
string name_;///<数据库名称
string path_;///<数据库文件存放的目录
unordered_map<string,Table*> opened_tables_;///<当前所有打开的表
unique_ptr<BufferPoolManager> buffer_pool_manager_;///<当前数据库的bufferpool管理器
unique_ptr<LogHandler> log_handler_;///<当前数据库的日志处理器
unique_ptr<TrxKit> trx_kit_;///<当前数据库的事务管理器

///给每个table都分配一个ID，用来记录日志。这里假设所有的DDL都不会并发操作，所以相关的数据都不上锁
int32_t next_table_id_ = 0;

LSN check_point_lsn_ = 0;///<当前数据库的检查点LSN。会记录到磁盘中。
```

## Table

```cpp
Db*db_=nullptr;
string base_dir_;
TableM etatable_meta_;
DiskBufferPool* data_buffer_pool_ = nullptr;///数据文件关联的bufferpool
RecordFileHandler* record_handler_ = nullptr;///记录操作
vector<Index*> indexes_;
```

在parser之后的解析阶段，sqlnode中的table字符串就会被绑定为程序内部使用的数据结构。以上是一个table对象持有的字段。包括db，存储路径，bufferpoll，recordHandler，跟表关联的索引。

定义了一系列方法，插入一行，删除一行，更新一行，创建一行内容。

可以预想到的是，当我们要插入一行数据时，肯定是通过DB对象，给定一个tablename，然后获取到table对象，然后使用make_record创建一行记录，然后执行插入。

还有table_meta类。一般有meta的就是元数据类，存储一个类的特征。

```cpp
int32_t table_id_ = -1;
string name_;
vector<FieldMeta> trx_fields_;
vector<FieldMeta> fields_;//包含sys_fields
vector<IndexMeta> indexes_;
StorageFormat storage_format_;

intrecord_size_=0;
```

tablei_id，名字，系统内部trx_fields（mvcc，或者null），字段，索引，存储格式。做简单了解即可，知道在系统内部一个表身上承载的功能。

## Field

```cpp
class Field {
public:
    Field() = default;

    Field(const Table* table, const FieldMeta* field)
        : table_(table), field_(field) {}

    Field(const Field&) = default;

    const Table* table() const { return table_; }
    const FieldMeta* meta() const { return field_; }

    AttrType attr_type() const { return field_->type(); }

    const char* table_name() const { return table_->name(); }
    const char* field_name() const { return field_->name(); }

    void set_table(const Table* table) { this->table_ = table; }
    void set_field(const FieldMeta* field) { this->field_ = field; }

    void set_int(Record& record, int value);
    int get_int(const Record& record);

    const char* get_data(const Record& record);

private:
    const Table* table_ = nullptr;
    const FieldMeta* field_ = nullptr;
};
```

字段类，表持有多个字段。通过访问字段类，我们可以知道这个列的元数据信息，什么类型，占多长。同样他也有一个元数据类，记录了名字类型位置长度可见性和id。

```cpp
string name_;          // 字段名称
AttrType attr_type_;   // 字段属性类型
int attr_offset_;      // 字段在记录中的偏移量
int attr_len_;         // 字段长度
bool visible_;         // 是否可见
int field_id_;         // 字段ID
```

## Index

![索引目录类](https://huanghuoguoguo.github.io/images/1740116213047-2dd2f201-f7ab-4c77-a9c0-c4935ce87195.png)

索引是数据库中非常重要的部分。但是如果这部分比较复杂，可以先决定跳过。当编写null或者uniqueindex时自然需要学习这部分的知识。

在基本的逻辑上，MiniOB的B+Tree和常规意义上的B+Tree是一致的，查询和插入都是从根逐层定位到叶结点，然后在叶结点内获取或者插入。如果插入过程发生叶结点满的情况，同样会进行分裂，并向上递归这一过程。

![叶子节点结构](https://huanghuoguoguo.github.io/images/1740116245408-c395146f-50ad-4d41-a446-f3e614161549.png)

如上图，每个结点组织成一个固定大小的page，之前介绍过每个page首先有一个page_num表示page在文件中的序号，每个结点page都有一个commonheader实现为IndexNode结构，其中包括is_leaf（是否为叶结点）、key_num（结点中key的个数）、parent（结点父结点的pagenum），当parent=-1时表示该结点没有父结点。

除此之外，Leafpage还有prev_brother（左结点的pagenum）和next_brother（右结点的pagenum），这两项用于帮助遍历。最后page所剩下的空间就顺序存放键值对，叶结点所存放的key是索引列的值加上RID（该行数据在磁盘上的位置），Value则为RID，也就是说键值数据都是存放在叶结点上的，和B+Tree中叶结点的值是指向记录的指针不同。

![内部节点结构示意图](https://huanghuoguoguo.github.io/images/1740116245491-bdb1f09e-d89a-4d7e-bc32-c2e2874c6eb0.png)

内部结点和叶结点有两点不同，一个是没有左右结点的pagenum；另一个是所存放的值是pagenum，也就是标识了子结点的page位置。如上图所示，键值对在内部结点是这样表示的，第一个键值对中的键是一个无效数据，真正用于比较的只有k1和k2。

![索引文件](https://huanghuoguoguo.github.io/images/1740116245501-6be00985-5efd-4256-8982-89ba4cab8169.png)

所有的结点（即page）都存储在外存的索引文件IndexFile中，其中文件的第一个page是索引文件头，存储了一些元数据，如rootpage的pagenum，内部结点和叶子结点能够存储键值对的最大个数等。

![img](https://huanghuoguoguo.github.io/images/1740116245465-ade547d5-8f8a-4894-ada2-b2f6c5433a55.png)

上图是一个简单的MiniOB B+Tree示例，其中叶结点能够访问到左右结点，并且每个结点能够访问到父结点。我们能够从IndexFile的第一个page得到rootpage，而在知道一棵B+Tree的root page以后就足够访问到任意一个结点了。查询时我们会从root page开始逐层向下定位到目标叶结点，在每个page内遍历搜索查找键。

### 插入

在插入时，我们首先定位到叶结点，如下图中的page2，然后在结点内定位一个插入位置，如果结点未满，那么将键值对插入指定位置并向后移动部分数据即可；如果结点已满，那么需要对其进行分裂。

我们将先创建一个新的右兄弟结点，即page5，然后在原结点内保留前一半的键值对，剩余的键值对则移动到新结点，并修改page2的后向page num，page5的前后向page num以及page4的前向pag enum，再根据之前定位的插入位置判断是插入page2还是page5，完成叶结点的插入。

![page](https://huanghuoguoguo.github.io/images/1740116245502-ef9c8f6b-b8da-497f-ba09-406e51d0d069.png)

此外，由于我们新增了结点，我们需要在父结点也插入新的键值对，这一步将涉及到原结点，新结点以及新结点中的最小键，分为以下两种情况：

1. 有父结点，那么直接将新结点中的最小键以及新结点的page num作为键值对插入父结点即可。 ![插入](https://huanghuoguoguo.github.io/images/1740116245805-8f7f51c9-da48-4f4d-852d-6792d6dcff36.png)
2. 假设此时没有父结点，那么我们将创建一个新的根结点，除了把新结点键值对插入，还会将原结点的page num作为第一个键值对的值进行插入。

![分裂](https://huanghuoguoguo.github.io/images/1740116245878-22851daa-880d-452f-b6c7-f30d0151afce.png)

如果父结点的键值对插入同样触发了分裂，我们将按上述的步骤递归执行。

### 删除

正常的删除操作我们就不再介绍，这里介绍一些涉及结点合并的特殊情况。

首先在结点内删除键值对，然后判断其中的键值对数目是否小于一半，如果是则需要进行特殊处理。比如page2中删除一个键值对，导致其键值对数目小于一半，此时通过它的父结点找到该结点的左兄弟，如果是最左边的结点，则找到其右兄弟。

![page连接](https://huanghuoguoguo.github.io/images/1740116245941-2fa207dc-edbb-4fb5-897b-2ff07e85df6f.png)

- 如果两个结点的所有键值对能容纳在一个结点内，那么进行合并操作，将右结点的数据迁移到左结点，并删除父结点中指向右结点的键值对。

![page迁移](https://huanghuoguoguo.github.io/images/1740116245955-237e81c8-8d2c-45a1-9324-d11e38ba2c19.png)

- 如果两个结点的所有键值对不能容纳在一个结点内，那么进行重构操作。

- 当所删除键值对的结点不是第一个结点时，那么选择将左兄弟的最后一个键值对移动到当前结点，并修改父结点中指向当前结点的键。

![page](https://huanghuoguoguo.github.io/images/1740116245977-f46f4e54-7b8c-4ba6-852d-59a12c627a47.png)

- 当所删除键值对的结点是第一个结点时，那么选择将右兄弟的第一个键值对移动到当前结点，并修改父结点中指向右兄弟的键。

![page](https://huanghuoguoguo.github.io/images/1740116246234-ce8333ea-2580-4214-97e3-47e45ca35db6.png)

在上述两种操作中，合并操作会导致父结点删除键值对，因此会向上递归地去判断是否需要再次的合并与重构。

有一个向量索引的赛题，就需要我们添加一个操作向量索引的index。



## Record

```cpp
private:
    RIDrid_;

    char* data_ = nullptr;
    int len_ = 0;///如果不是record自己来管理内存，这个字段可能是无效的
    bool owner_ = false;///表示当前是否由record来管理内存
```

record持有rid，data地址，长度。

rid需要简单解释一下。总的来说就是一行记录在哪个页面，在页面中的哪个位置。通过这个RID可以具体定位到唯一一条记录。

```cpp
/**
 * @brief 标识一个记录的位置。
 * 一个记录是放在某个文件的某个页面的某个槽位。这里不记录文件信息，仅记录页面和槽位信息。
 */
struct RID {
    PageNum page_num;  // 记录所在的页面编号
    SlotNum slot_num;  // 记录所在的槽位编号

    RID() = default;

    RID(const PageNum _page_num, const SlotNum _slot_num)
        : page_num(_page_num), slot_num(_slot_num) {}

    /**
     * @brief 比较两个 RID 的大小。
     * 先比较页面编号，如果相同则比较槽位编号。
     * @param rid1 第一个 RID。
     * @param rid2 第二个 RID。
     * @return 比较结果，小于0表示 rid1 < rid2，等于0表示 rid1 == rid2，大于0表示 rid1 > rid2。
     */
    static int compare(const RID* rid1, const RID* rid2) {
        int page_diff = rid1->page_num - rid2->page_num;
        if (page_diff != 0) {
            return page_diff;
        } else {
            return rid1->slot_num - rid2->slot_num;
        }
    }
};
```

在record目录下还有log_handler，record_manager，他们管理我们认识当中的那几个log，这里不展开详细讲，只需要知道有他们存在，并且相当于一个管家，负责和其他模块交互即可。

### 代码中的注释

表记录管理的内容包括如何在文件上存放、读取、检索。也就是记录的增删改查。这里的文件都会被拆分成页面，每个页面都有一样的大小。更详细的信息可以参考BufferPool。按照BufferPool的设计，第一个页面用来存放BufferPool本身的元数据，比如当前文件有多少页面、已经分配了多少页面、每个页面的分配状态等。所以第一个页面对RecordManager来说没有作用。RecordManager本身没有再单独拿一个页面来存放元数据，每一个页面都存放了一个页面头信息，也就是每个页面都有RecordManager的元数据信息，可以参考PageHeader，这虽然有点浪费但是做起来简单。

对单个页面来说，最开始是一个页头，然后接着就是一行行记录（会对齐）。

如何标识一个记录，或者定位一个记录？

使用RID，即recordidentifier。使用pagenum表示所在的页面，slotnum表示当前在页面中的位置。因为这里的

记录都是定长的，所以根据slotnum可以直接计算出记录的起始位置。

问题1：那么如果记录不是定长的，还能使用slotnum吗？

问题2：如何更有效地存放不定长数据呢？

问题3：如果一个页面不能存放一个记录，那么怎么组织记录存放效果更好呢？



按照上面的描述，这里提供了几个类，分别是：

- RecordFileHandler：管理整个文件/表的记录增删改查
- RecordPageHandler：管理单个页面上记录的增删改查
- RecordFileScanner：可以用来遍历整个文件上的所有记录
- RecordPageIterator：可以用来遍历指定页面上的所有记录
- PageHeader：每个页面上都会记录的页面头信息

## Buffer

![buffer目录](https://huanghuoguoguo.github.io/images/1740117699296-6b3b0638-1aac-4ecf-a0e8-dc8967dabf61.png)

在 MiniOB 项目中，`buffer` 目录下的几个类分别承担着不同的职责，它们共同协作以实现数据的高效存储和访问。

- buffer_pool_log（简单了解）

- **作用**：`buffer_pool_log` 类主要用于管理缓冲池的日志记录。它记录了缓冲池中数据的修改操作，以便在系统崩溃或重启时进行数据恢复。日志记录是确保数据持久性和一致性的关键机制。
- **注意事项**：在使用 `buffer_pool_log` 时，需要注意日志的写入时机和顺序，确保日志的完整性和一致性。此外，日志文件的管理和清理也需要定期进行，以避免日志文件过大导致的性能问题。

- disk_buffer_pool（重点理解）

- **作用**：`disk_buffer_pool` 类负责管理磁盘上的缓冲区。它将磁盘文件划分为多个固定大小的页面，并在内存中维护这些页面的缓存。当需要访问磁盘上的数据时，`disk_buffer_pool` 会先检查内存中的缓存，如果缓存中没有所需页面，则从磁盘读取并加载到缓存中。
- **注意事项**：在使用 `disk_buffer_pool` 时，需要注意缓存的管理策略，如缓存的大小、缓存的替换算法等。此外，还需要注意磁盘 I/O 的性能优化，尽量减少磁盘读写操作的次数。

- double_write_buffer

- **作用**：`double_write_buffer` 类实现了双写缓冲区机制，用于解决页面写入的原子性问题。当有数据页需要写入磁盘时，`double_write_buffer` 会先将数据写入一个共享的缓冲区（双写缓冲区），然后再从双写缓冲区写入实际的数据文件。这样可以确保即使在写入过程中发生系统崩溃，数据文件中的页面也不会处于不一致的状态。
- **注意事项**：在使用 `double_write_buffer` 时，需要注意双写缓冲区的大小和管理策略。双写缓冲区会增加额外的磁盘 I/O 操作，可能会影响性能，因此需要在性能和数据一致性之间找到平衡点。

- frame

- **作用**：`frame` 类表示缓冲池中的一个页面帧。每个页面帧对应磁盘上的一个页面，用于在内存中存储页面数据。`frame` 类提供了对页面数据的访问和操作方法，如读取、写入、标记为脏页等。
- **注意事项**：在使用 `frame` 时，需要注意页面帧的状态管理，如是否被固定、是否为脏页等。此外，还需要注意页面帧的生命周期管理，确保在适当的时候释放页面帧，避免内存泄漏。

- page

- **作用**：`page` 类表示一个数据页面，是数据存储的基本单位。每个页面包含一定数量的数据记录，并且具有固定的大小。`page` 类提供了对页面数据的访问和操作方法，如读取、写入、插入、删除等。
- **注意事项**：在使用 `page` 时，需要注意页面的大小和数据结构。页面的大小通常与系统架构和磁盘块大小有关，需要根据实际情况进行配置。此外，还需要注意页面的数据结构设计，确保数据的高效存储和访问。

这些类在 MiniOB 项目中共同协作，实现了数据的高效存储和访问。`buffer_pool_log` 确保了数据的一致性和持久性，`disk_buffer_pool` 提供了磁盘数据的缓存管理，`double_write_buffer` 解决了页面写入的原子性问题，`frame` 和 `page` 则分别表示内存中的页面帧和磁盘上的数据页面。通过合理使用这些类，可以显著提高数据库系统的性能和可靠性。

## Trx

![索引目录](https://huanghuoguoguo.github.io/images/1740117716249-f483bff5-d783-4725-9f10-4446340da062.png)

目前默认是无事务模式，也就是默认单线程执行，不做任何mvcc并发控制。如果需要做mvcc的赛题，具体是修改这部分代码。mvcc的篇幅较多，同时也比较专业，这里不做阐述。
