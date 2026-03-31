/**
 * 基本数据类型 vs 包装类型 性能对比实验
 *
 * 验证要点：
 * 1. 内存占用差异
 * 2. 顺序遍历求和性能（体现 cache 友好性）
 * 3. 随机访问性能（体现指针追逐的开销）
 *
 * 使用方式：
 *   javac PrimitiveVsWrapperBenchmark.java
 *   java -Xmx2g PrimitiveVsWrapperBenchmark
 *
 * 可选：配合 perf stat 观察硬件级 cache miss
 *   perf stat -e cache-misses,cache-references,L1-dcache-load-misses java -Xmx2g PrimitiveVsWrapperBenchmark
 */
public class PrimitiveVsWrapperBenchmark {

    // 数组大小：足够大以超出 L2 cache（通常 256KB~1MB），体现 cache miss 差异
    private static final int SIZE = 4_000_000;
    // 预热轮次：让 JIT 充分编译
    private static final int WARMUP_ROUNDS = 5;
    // 正式测量轮次
    private static final int MEASURE_ROUNDS = 10;

    // ==================== 数据准备 ====================

    private static int[] primitiveArray;
    private static Integer[] wrapperArray;
    private static Integer[] wrapperArrayScattered; // 故意打散的包装类型数组

    private static void prepareData() {
        // 1) 基本类型数组 —— 连续内存
        primitiveArray = new int[SIZE];
        for (int i = 0; i < SIZE; i++) {
            primitiveArray[i] = i;
        }

        // 2) 包装类型数组 —— 顺序 new，TLAB 可能让它们暂时相邻
        wrapperArray = new Integer[SIZE];
        for (int i = 0; i < SIZE; i++) {
            wrapperArray[i] = new Integer(i); // 故意用 new 避免 Integer 缓存
        }

        // 3) 故意打散的包装类型数组 —— 模拟 GC 后对象散落
        //    先创建大量干扰对象把堆搅乱，再交错分配
        Object[] junk = new Object[SIZE];
        wrapperArrayScattered = new Integer[SIZE];
        for (int i = 0; i < SIZE; i++) {
            junk[i] = new byte[32]; // 干扰对象，占据堆空间
            wrapperArrayScattered[i] = new Integer(i);
        }
        junk = null; // 释放干扰对象，但 Integer 已经散落在各处
        System.gc(); // 建议 GC，进一步打乱布局
    }

    // ==================== 测试 1：顺序求和 ====================

    private static long sumPrimitive() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += primitiveArray[i];
        }
        return sum;
    }

    private static long sumWrapper() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += wrapperArray[i]; // 自动拆箱 + 指针解引用
        }
        return sum;
    }

    private static long sumWrapperScattered() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += wrapperArrayScattered[i];
        }
        return sum;
    }

    // ==================== 测试 2：随机访问求和 ====================

    private static int[] randomIndices;

    private static void prepareRandomIndices() {
        randomIndices = new int[SIZE];
        java.util.Random rng = new java.util.Random(42);
        for (int i = 0; i < SIZE; i++) {
            randomIndices[i] = rng.nextInt(SIZE);
        }
    }

    private static long randomAccessPrimitive() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += primitiveArray[randomIndices[i]];
        }
        return sum;
    }

    private static long randomAccessWrapper() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += wrapperArray[randomIndices[i]];
        }
        return sum;
    }

    private static long randomAccessWrapperScattered() {
        long sum = 0;
        for (int i = 0; i < SIZE; i++) {
            sum += wrapperArrayScattered[randomIndices[i]];
        }
        return sum;
    }

    // ==================== 测试 3：内存占用估算 ====================

    private static void estimateMemory() {
        Runtime rt = Runtime.getRuntime();

        // 测量 int[] 占用
        System.gc(); System.gc();
        long before = rt.totalMemory() - rt.freeMemory();
        int[] tempPrimitive = new int[SIZE];
        for (int i = 0; i < SIZE; i++) tempPrimitive[i] = i;
        long afterPrimitive = rt.totalMemory() - rt.freeMemory();
        long primitiveBytes = afterPrimitive - before;

        // 测量 Integer[] 占用
        tempPrimitive = null;
        System.gc(); System.gc();
        before = rt.totalMemory() - rt.freeMemory();
        Integer[] tempWrapper = new Integer[SIZE];
        for (int i = 0; i < SIZE; i++) tempWrapper[i] = new Integer(i);
        long afterWrapper = rt.totalMemory() - rt.freeMemory();
        long wrapperBytes = afterWrapper - before;

        tempWrapper = null;

        System.out.println("============================================");
        System.out.println("  内存占用估算 (数组大小: " + SIZE + ")");
        System.out.println("============================================");
        System.out.printf("  int[]     : %,d bytes (%.1f MB)%n", primitiveBytes, primitiveBytes / 1024.0 / 1024.0);
        System.out.printf("  Integer[] : %,d bytes (%.1f MB)%n", wrapperBytes, wrapperBytes / 1024.0 / 1024.0);
        System.out.printf("  膨胀倍数   : %.1fx%n", (double) wrapperBytes / primitiveBytes);
        System.out.printf("  每个 int  占: %d bytes%n", 4);
        System.out.printf("  每个 Integer 约占: %d bytes (含对象头+对齐)%n", wrapperBytes / SIZE);
        System.out.println();
    }

    // ==================== 测量框架 ====================

    @FunctionalInterface
    interface LongSupplier {
        long get();
    }

    /**
     * 先预热若干轮（让 JIT 编译），再正式测量取中位数
     */
    private static double benchmark(String label, LongSupplier task) {
        // 预热
        for (int i = 0; i < WARMUP_ROUNDS; i++) {
            task.get();
        }

        // 正式测量
        long[] times = new long[MEASURE_ROUNDS];
        long result = 0;
        for (int i = 0; i < MEASURE_ROUNDS; i++) {
            long start = System.nanoTime();
            result = task.get();
            long end = System.nanoTime();
            times[i] = end - start;
        }

        // 取中位数，避免 GC 毛刺
        java.util.Arrays.sort(times);
        double medianMs = times[MEASURE_ROUNDS / 2] / 1_000_000.0;

        System.out.printf("  %-30s : %8.2f ms  (checksum=%d)%n", label, medianMs, result);
        return medianMs;
    }

    // ==================== 单项测试（供 perf stat 隔离运行） ====================

    /**
     * 只跑指定测试，用于 perf stat 精确观测
     * 用法: java PrimitiveVsWrapperBenchmark <test>
     *   test = seq-primitive | seq-wrapper | rand-primitive | rand-wrapper | all
     */
    private static void runIsolatedTest(String test) {
        prepareData();
        prepareRandomIndices();
        int rounds = 20; // 多跑几轮让 perf 有足够采样

        switch (test) {
            case "seq-primitive":
                System.out.println("[perf] 顺序遍历 int[] x" + rounds);
                for (int i = 0; i < rounds; i++) sumPrimitive();
                break;
            case "seq-wrapper":
                System.out.println("[perf] 顺序遍历 Integer[] x" + rounds);
                for (int i = 0; i < rounds; i++) sumWrapper();
                break;
            case "rand-primitive":
                System.out.println("[perf] 随机访问 int[] x" + rounds);
                for (int i = 0; i < rounds; i++) randomAccessPrimitive();
                break;
            case "rand-wrapper":
                System.out.println("[perf] 随机访问 Integer[] x" + rounds);
                for (int i = 0; i < rounds; i++) randomAccessWrapper();
                break;
            default:
                System.out.println("未知测试: " + test);
                System.out.println("可选: seq-primitive, seq-wrapper, rand-primitive, rand-wrapper, all");
        }
    }

    // ==================== 主函数 ====================

    public static void main(String[] args) {
        // 如果传了参数，执行单项隔离测试（给 perf stat 用）
        if (args.length > 0 && !args[0].equals("all")) {
            runIsolatedTest(args[0]);
            return;
        }

        System.out.println();
        System.out.println("  Java Primitive vs Wrapper Benchmark");
        System.out.println("  JVM: " + System.getProperty("java.vm.name") + " " + System.getProperty("java.vm.version"));
        System.out.println("  数组大小: " + String.format("%,d", SIZE) + " 元素");
        System.out.println("  预热: " + WARMUP_ROUNDS + " 轮, 测量: " + MEASURE_ROUNDS + " 轮 (取中位数)");
        System.out.println();

        // 内存占用
        estimateMemory();

        // 准备数据
        System.out.println("  准备测试数据...");
        prepareData();
        prepareRandomIndices();
        System.out.println();

        // 顺序遍历
        System.out.println("============================================");
        System.out.println("  测试 1：顺序遍历求和 (体现 cache 局部性)");
        System.out.println("============================================");
        double t1 = benchmark("int[] 顺序求和", PrimitiveVsWrapperBenchmark::sumPrimitive);
        double t2 = benchmark("Integer[] 顺序求和", PrimitiveVsWrapperBenchmark::sumWrapper);
        double t3 = benchmark("Integer[] 打散后顺序求和", PrimitiveVsWrapperBenchmark::sumWrapperScattered);
        System.out.printf("  → Integer[]/int[] = %.1fx 慢%n", t2 / t1);
        System.out.printf("  → Integer[] 打散/int[] = %.1fx 慢%n", t3 / t1);
        System.out.println();

        // 随机访问
        System.out.println("============================================");
        System.out.println("  测试 2：随机访问求和 (体现指针追逐开销)");
        System.out.println("============================================");
        double t4 = benchmark("int[] 随机访问", PrimitiveVsWrapperBenchmark::randomAccessPrimitive);
        double t5 = benchmark("Integer[] 随机访问", PrimitiveVsWrapperBenchmark::randomAccessWrapper);
        double t6 = benchmark("Integer[] 打散后随机访问", PrimitiveVsWrapperBenchmark::randomAccessWrapperScattered);
        System.out.printf("  → Integer[]/int[] = %.1fx 慢%n", t5 / t4);
        System.out.printf("  → Integer[] 打散/int[] = %.1fx 慢%n", t6 / t4);
        System.out.println();

        // 总结
        System.out.println("============================================");
        System.out.println("  结论");
        System.out.println("============================================");
        System.out.println("  1. int[] 内存紧凑，CPU cache 友好，遍历速度最快");
        System.out.println("  2. Integer[] 每次访问需要解引用指针（拆箱），cache miss 增加");
        System.out.println("  3. 对象在堆中越分散，cache miss 越严重，性能越差");
        System.out.println("  4. 随机访问场景下差距进一步放大（prefetch 失效）");
        System.out.println();
        System.out.println("  建议：CPU 密集型计算优先使用基本类型数组，");
        System.out.println("        或使用 Eclipse Collections / HPPC 等原始类型集合库。");
        System.out.println();
    }
}
