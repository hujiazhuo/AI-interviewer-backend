# Java 后端开发工程师面试题库

---

## 一、Java 基础

### JDK、JRE、JVM 三者的关系？

- **JDK**：Java Development ToolKit，Java 开发工具箱，提供开发和运行环境
- **JRE**：Java Runtime Environment，Java 运行环境
- **JVM**：Java 虚拟机，Java 跨平台核心
- **关系**：JRE = JVM + Java 核心类库；JDK = JRE + Java 工具 + 编译器 + 调试器

### == 和 equals 的区别是什么？

- **== 运算符**：
  - 基本类型：比较值
  - 引用类型：比较内存地址
- **equals()**：
  - 引用类型默认和 == 一样比较地址
  - 重写后比较内容（如 String、Integer）

### Java 中的几种基本数据类型？

8 种：

- 整数：byte、short、int、long
- 浮点：float、double
- 字符：char
- 布尔：boolean

### 存储金额用什么数据类型？

使用 **BigDecimal**，精确计算，避免浮点数精度丢失。

### 内部类和静态内部类的区别？

- **生命周期**：内部类绑定外部实例；静态内部类无关
- **访问权限**：内部类可访问所有成员；静态内部类只能访问静态成员
- **创建方式**：内部类需要外部实例；静态内部类不需要

### 静态变量和实例变量的区别？

- **静态变量**：static 修饰，类加载初始化，方法区，所有对象共享
- **实例变量**：无 static，对象创建初始化，堆内存，对象独有

### final 关键字的作用？

- 修饰引用：值/地址不可变
- 修饰方法：不能重写
- 修饰类：不能继承

### 接口和抽象类的区别？

- 抽象类用 extends，接口用 implements
- 抽象类可有构造，接口没有
- 类只能继承一个抽象类，可实现多个接口

### String、StringBuffer 和 StringBuilder 的区别？

- **String**：不可变
- **StringBuilder**：非线程安全，效率最高
- **StringBuffer**：线程安全（synchronized），效率次之

### Object 的常用方法？

toString、equals、hashCode、clone、getClass、wait、notify、notifyAll

### 为什么重写 equals() 时必须重写 hashCode()？

相等对象必须 hashCode 相等，否则 HashMap/HashSet 异常。

### Java 创建对象有几种方式？

new、反射、clone、反序列化。

### final、finally、finalize 的区别？

- **final**：不可变、不可重写、不可继承
- **finally**：异常处理一定执行
- **finalize**：GC 前调用，已废弃

### 重载和重写的区别？

- **重载**：同一个类，方法名同，参数不同
- **重写**：子类重写父类，方法签名一致

### 什么是反射？

运行时获取类信息、调用方法、操作属性的机制。

### 反射常见的应用场景？

动态代理、JDBC 加载驱动、BeanUtils、RPC、ORM、Spring IOC/AOP。

### 什么是 AIO、BIO 和 NIO？

- **BIO**：同步阻塞
- **NIO**：同步非阻塞
- **AIO**：异步非阻塞

### 序列化和反序列化？

- **序列化**：对象 → 字节流
- **反序列化**：字节流 → 对象

### 深拷贝和浅拷贝的区别？

- **浅拷贝**：复制引用
- **深拷贝**：复制整个对象树

### Java8 的新特性？

Lambda、Stream、默认方法、Optional、新日期 API。

---

## 二、集合框架

### 常见的集合有哪些？

- **Collection**：List、Set、Queue
- **Map**：HashMap、ConcurrentHashMap 等

### ArrayList 和 LinkedList 的区别？

- **ArrayList**：数组，查询快，增删慢
- **LinkedList**：双向链表，增删快，查询慢

### Arraylist 和 Vector 的区别？

- ArrayList 扩容 1.5 倍，Vector 2 倍
- Vector 线程安全，效率低

### HashMap 和 Hashtable 的区别？

- HashMap 允许 null，线程不安全
- Hashtable 不允许 null，线程安全

### 哪些集合类是线程安全的？哪些不安全？

- **安全**：Vector、Hashtable、ConcurrentHashMap、Stack
- **不安全**：HashMap、ArrayList、LinkedList、HashSet、TreeSet、TreeMap

### HashMap 原理？

JDK1.8：数组 + 链表 + 红黑树。链表≥8 转树，≤6 退链。

### 解决 hash 冲突的方法？

链表法、开放地址法、再 hash、公共溢出区。

### Set 是怎么去重的？

底层 HashMap，key 唯一，需 hashCode+equals 保证去重。

### ConcurrentHashMap 原理？

- **JDK7**：分段锁 Segment
- **JDK8**：CAS + synchronized 锁头节点

---

## 三、并发编程

### 并发和并行的区别？

- **并发**：交替执行
- **并行**：同时执行

### 线程和进程的区别？

- **进程**：资源分配单位
- **线程**：CPU 调度单位

### 线程有哪些状态？

NEW、RUNNABLE、BLOCKED、WAITING、TIME_WAITING、TERMINATED

### 创建线程的方式？

继承 Thread、实现 Runnable、实现 Callable、线程池。

### start() 和 run() 的区别？

- **start()**：启动线程
- **run()**：普通方法调用

### 什么是 CAS？

Compare And Swap，乐观锁实现，无锁并发。

### 同步和异步的区别？

- **同步**：等待结果
- **异步**：不等待

### 如何实现线程同步？

synchronized、Lock、volatile、ThreadLocal、原子类、线程池。

### 什么是线程死锁？

互相持有对方资源，循环等待。四条件：互斥、请求保持、不可剥夺、循环等待。

### 如何避免线程死锁？

统一加锁顺序、超时、减少锁粒度、避免嵌套锁。

### wait 和 sleep 的区别？

- wait 释放锁，sleep 不释放
- wait 需在同步块，sleep 不需要

### volatile 关键字有什么用？

可见性、禁止指令重排，不保证原子性。

### 什么是 ThreadLocal？

线程本地变量，隔离数据，避免线程安全问题。内存泄漏：必须 remove()。

### 为什么要用线程池？

减少创建销毁开销、控制并发、复用线程、管理任务。

### 线程池常见参数？

corePoolSize、maximumPoolSize、workQueue、keepAliveTime、unit、threadFactory、handler

### 线程池的拒绝策略？

AbortPolicy、CallerRunsPolicy、DiscardPolicy、DiscardOldestPolicy

### 线程池的工作原理？

核心线程 → 队列 → 最大线程 → 拒绝策略

### synchronized 的作用？

原子性、可见性、有序性。

### synchronized 锁升级过程？

偏向锁 → 轻量级锁 → 重量级锁

---

## 四、JVM

### JVM 内存结构 (JDK1.8)

- **线程私有**：程序计数器、虚拟机栈、本地方法栈
- **线程共享**：堆、元空间

### 堆内存结构 (JDK1.8)

新生代（Eden:S0:S1=8:1:1）、老年代。

### GC 垃圾回收

- **如何发现垃圾**：引用计数、可达性分析
- **如何回收**：标记清除、复制、标记整理、分代收集

### 什么是 STW？

Stop-The-World，GC 时暂停所有用户线程。

### 垃圾回收器？

CMS、G1（JDK9 默认）

### JVM 故障诊断工具？

jps、jinfo、jhat、jstat、jmap、jstack

### JAVA 类加载器有哪些？

启动类加载器、扩展类加载器、应用程序类加载器、自定义类加载器

### 双亲委派机制？

父类加载器优先加载，安全、避免重复。

### 内存泄漏和内存溢出的区别？

- **内存泄漏**：用不完不释放
- **内存溢出**：不够用

---

## 五、Spring 全家桶

### Spring 的优点？

轻量、松耦合、AOP、声明式事务、易集成、易测试。

### 什么是 Spring AOP？

面向切面编程，抽离公共逻辑，减少重复代码。

### JDK 动态代理和 CGLIB 动态代理的区别？

- **JDK**：接口代理
- **CGLIB**：继承代理

### Spring 通知有哪些类型？

前置、后置、返回、异常、环绕

### 什么是 Spring IOC？

控制反转，容器管理 Bean，解耦。

### Spring 中 Bean 的作用域？

singleton、prototype、request、session、application

### Spring 中 Bean 的生命周期？

实例化 → 属性填充 → 初始化 → 使用 → 销毁

### 依赖注入的方式？

构造器、setter、字段注入

### @Autowired 和 @Resource 的区别？

- **@Autowired**：按类型
- **@Resource**：按名称

### Spring 事务隔离级别？

读未提交、读已提交、可重复读（MySQL 默认）、串行化

### Spring 事务传播属性？

REQUIRED、REQUIRES_NEW、SUPPORTS、MANDATORY、NEVER、NESTED 等

### Spring 事务在什么情况下会失效？

非 public、自调用、数据库不支持、异常不匹配、传播属性错误、catch 未抛出、未纳入容器、异步

### Spring MVC 工作原理？

DispatcherServlet → HandlerMapping → HandlerAdapter → Controller → ModelAndView → ViewResolver → 渲染

### Spring Boot 自动装配原理？

@EnableAutoConfiguration → 读取 spring.factories → 条件装配

---

## 六、MySQL

### InnoDB 与 MyISAM 引擎区别？

- **InnoDB**：事务、行锁、外键、崩溃恢复
- **MyISAM**：无事务、表锁、查询快

### in 和 exists 的区别？

- **in**：适合子查询结果集小
- **exists**：适合主查询小

### CHAR 和 VARCHAR 的区别？

CHAR 固定长度，VARCHAR 可变长度。

### 索引失效的几种情况？

like % xx、隐式转换、or、not in、函数、!=、<>、is null/is not null

### 什么是索引下推？

在引擎层过滤，减少回表。

### 数据库锁有哪些？

表锁、行锁、间隙锁、临键锁

### B 树与 B+ 树的区别？

B+ 树叶子有序链表、范围查询更快、IO 更少

### 分库分表的优缺点？

- **优点**：提高并发、减轻单库压力
- **缺点**：复杂、事务难、跨节点查询难

---

## 七、Redis

### Redis 到底是多线程还是单线程？

单线程核心，6.0 后多线程 IO

### Redis 数据持久化机制？

RDB、AOF、混合持久化

### Redis 是单线程，但为什么快？

纯内存、IO 多路复用、避免线程切换

### Redis 过期删除策略？

惰性删除、定期删除

### Redis 内存淘汰策略？

volatile-lru、allkeys-lru、volatile-random、allkeys-random、volatile-ttl、noeviction

### Redis 缓存穿透、击穿、雪崩？

- **穿透**：查不存在数据 → 布隆过滤器、缓存空值
- **击穿**：热点 key 失效 → 互斥锁、永不过期
- **雪崩**：大量 key 同时过期 → 随机过期、集群、降级

### 数据库和缓存的一致性？

先更数据库，再删缓存。最终一致：延迟双删、分布式锁

### 什么是分布式锁？

SETNX + 过期时间。Redisson 可重入、阻塞、自动续期。

---

## 八、消息队列

### RabbitMQ 为什么用 MQ？

异步、削峰、解耦

### Exchange 类型？

direct、topic、fanout、headers

### 如何保证消息可靠性？

持久化、confirm、手动 ack

### 消息堆积怎么处理？

增加消费者、批量、优化消费逻辑

### 消息幂等性？

唯一 ID、去重表、状态机

---

## 九、微服务

### CAP 原则？

一致性、可用性、分区容忍性，三选二。

### Spring Cloud 核心组件？

Nacos（注册/配置）、Sentinel（限流熔断降级）、Gateway、OpenFeign、Seata（分布式事务）

### 分布式事务？

2PC、TCC、SAGA、Seata AT 模式

### Ribbon 负载均衡策略？

轮询、随机、加权、最小连接等

---

## 十、计算机网络

### TCP 三次握手和四次挥手？

- **三次握手**：建立连接
- **四次挥手**：断开连接

### TCP 粘包拆包？

流式传输无边界。解决：固定长度、分隔符、长度头。

### HTTP 和 HTTPS 的区别？

- **HTTP**：80 端口，明文传输
- **HTTPS**：443 端口，加密传输、身份认证、防篡改

### 跨域的解决方案？

同源策略。解决：CORS、代理、JSONP、postMessage

### Cookie、Session、JWT 的区别？

JWT 无状态、适合分布式；双 Token 无感刷新

---

## 十一、场景题

### 秒杀系统？

限流、异步、缓存、防超卖、分布式锁、削峰、降级

### 接口幂等？

唯一索引、token、状态机、分布式锁、防重表

### 高并发处理？

缓存、池化、异步、分库分表、索引优化、读写分离

### 分布式 ID？

雪花算法、号段模式、Redis 自增

---

## 十二、运维工具

### Linux 常用命令？

ps、netstat、top、df、free、grep、find、tar、chmod

### Docker 常用命令？

镜像、容器、Dockerfile、docker-compose、网络模式

### Arthas 常用命令？

dashboard、thread、trace、heap，线上排查神器

### 日志监控方案？

ELK、Prometheus+Grafana
