/********************************************************************************
 * @file    main.cpp
 * @brief   五传感器综合环境监测系统
 *
 * @note    传感器列表:
 *          ① SHT30  — 温湿度 (I2C, 0x44)
 *          ② SGP30  — eCO₂ + TVOC (I2C, 0x58)
 *          ③ 火焰1  — 红外火焰检测 (GPIO 数字量)
 *          ④ 火焰2  — 红外火焰检测 (GPIO 数字量)
 *          ⑤ MQ-3   — 乙醇浓度 (ADC 模拟量 + GPIO 数字报警)
 *
 * @note    报警输出:
 *          · 报警灯泡 → PIN_74 (任一传感器触发即亮)
 *          · 报警文件 → /tmp/alarm.txt (供外部程序读取状态)
 *
 * @note    日志文件:
 *          · 数据日志 → /home/root/env_log.csv (CSV 格式)
 *          · 报警事件 → /home/root/alarm_event.txt
 ********************************************************************************/

#include "main.hpp"
#include <time.h>
#include <math.h>

// ============================ 引脚定义 ============================

/* MQ-3 */
#define MQ3_DO_PIN              PIN_75
#define MQ3_ADC_CH              LS_ADC_CH0

/* 火焰传感器 */
#define FLAME1_DO_PIN           PIN_72
#define FLAME2_DO_PIN           PIN_73

/* 报警输出 */
#define BULB_PIN                PIN_74

// ============================ MQ-3 分压电路 ============================

#define DIVIDER_RATIO           3.0f    /* (20k+10k) / 10k  */

// ============================ MQ-3 参数 ============================

#define MQ3_VCC                 5.0f
#define MQ3_RL                  1.0f    /* 模块板载负载电阻 (kΩ) */
#define MQ3_CURVE_A             0.45f
#define MQ3_CURVE_B             (-0.872f)
#define MQ3_CLEAN_AIR           60.0f

// ============================ 报警阈值 ============================

/* MQ-3 乙醇 */
#define THR_ETHANOL_WARN        1.0f    /* 预警 (mg/L) */
#define THR_ETHANOL_ALARM       2.5f    /* 报警 (mg/L) */
#define THR_ETHANOL_RECOVER     1.5f    /* 恢复迟滞 (mg/L) */

/* SGP30 空气质量 (TVOC) */
#define THR_TVOC_WARN           500     /* 预警 (ppb) */
#define THR_TVOC_ALARM          1000    /* 报警 (ppb) */
#define THR_ECO2_WARN           1000    /* 预警 (ppm) */
#define THR_ECO2_ALARM          2000    /* 报警 (ppm) */

/* 温度 */
#define THR_TEMP_HIGH           50.0f   /* 高温报警 (℃) */

// ============================ MQ-3 趋势报警 ============================

#define TREND_WINDOW            10      /* 趋势分析窗口 (采样点数) */
#define TREND_SLOPE_THRESHOLD   0.03f   /* 上升速率阈值 (mg/L/s), 超此值触发趋势预警 */
#define TREND_MIN_CONC          0.3f    /* 趋势预警的最低起始浓度 (mg/L), 低浓度波动忽略 */

// ============================ 温湿度补偿 ============================

#define COMP_HUM_COEFF          0.12f   /* 湿度补偿系数 (每100%RH 修正12%) */
#define COMP_TEMP_COEFF         0.005f  /* 温度补偿系数 (每℃ 修正0.5%) */
#define COMP_REF_TEMP           25.0f   /* 参考温度 (℃) */
#define COMP_REF_HUM            50.0f   /* 参考湿度 (%RH) */

// ============================ 卡尔曼滤波 ============================

#define KF_PROCESS_NOISE        0.001f  /* 过程噪声 Q (小=信任模型) */
#define KF_MEASURE_NOISE        0.05f   /* 测量噪声 R (根据ADC噪声调) */
#define KF_INIT_UNCERTAINTY     1.0f    /* 初始不确定度 */

// ============================ EMA 自适应基线 ============================

#define EMA_ALPHA               0.005f  /* EMA平滑因子 (越小越慢, 0.005≈200秒响应) */
#define EMA_SIGMA_MULT          3.0f    /* 基线偏差倍数 */
#define EMA_MIN_SIGMA           0.05f   /* 最小标准差 */

// ============================ 互补滤波 (MQ-3 + SGP30) ============================

#define COMP_FILTER_K           0.75f   /* MQ-3 权重 (高频信任MQ-3) */
/* SGP30权重 = 1 - 0.75 = 0.25 (低频信任SGP30) */

// ============================ CUSUM 累积和检测 ============================

#define CUSUM_DRIFT             0.05f   /* 漂移参数 k (mg/L), 小于此的偏差视为噪声 */
#define CUSUM_THRESHOLD         1.5f    /* 报警阈值 h, 累积和超过此值触发 */
#define CUSUM_BONUS             15      /* CUSUM触发时风险额外加分 */

// ============================ 交叉验证阈值 ============================

#define XCHECK_TVOC_RISE        100     /* TVOC 同步上升阈值 (ppb), 超过此值视为与MQ-3一致 */

// ============================ 综合风险指数权重 ============================

#define RISK_W_MQ3              30      /* MQ-3 乙醇权重 */
#define RISK_W_FLAME            25      /* 火焰传感器权重 */
#define RISK_W_TVOC             20      /* SGP30 TVOC 权重 */
#define RISK_W_ECO2             15      /* SGP30 eCO2 权重 */
#define RISK_W_TEMP             10      /* 温度权重 */
#define RISK_BONUS_TREND        10      /* 趋势上升额外加分 */
#define RISK_BONUS_XCHECK       5       /* 交叉验证额外加分 */

/* 风险等级 */
#define RISK_SAFE               20
#define RISK_CAUTION            40
#define RISK_WARNING            60
#define RISK_SEVERE             80      /* 80+ = 危险 */

// ============================ 环境基线自学习 (EMA) ============================
#define SNAPSHOT_DIR            "/home/root/snapshots"  /* 事件快照目录 */

// ============================ 事件快照 ============================

#define SNAP_BUF_SIZE           30      /* 快照缓冲区 (30个采样 ≈ 报警前30秒) */
#define SNAP_FILE_MAX           20      /* 最多保留的快照文件数 */

// ============================ 传感器健康监控 ============================

#define HEALTH_STUCK_SAMPLES    300     /* 连续相同值判定卡死 (5分钟) */
#define HEALTH_FAIL_SAMPLES     10      /* 连续读失败判定掉线 */
#define HEALTH_CHECK_INTERVAL   60      /* 每60秒输出一次健康报告 */

// ============================ 采样与防抖 ============================

#define INTERVAL_MS             1000    /* 主循环间隔 1s */
#define WINDOW_SIZE             5       /* 滑动平均窗口 */
#define CONFIRM_CNT             3       /* 报警确认次数 */
#define CLEAR_CNT               5       /* 恢复确认次数 */
#define FLAME_CONFIRM_CNT       3       /* 火焰报警确认次数 */
#define FLAME_CLEAR_CNT         5       /* 火焰恢复确认次数 */

// ============================ 文件路径 ============================

#define LOG_CSV                 "/home/root/env_log.csv"
#define ALARM_FILE              "/tmp/alarm.txt"
#define CALIB_FILE              "/home/root/mq3_calib.txt"

// ============================ 终端颜色 ============================

#define CLR_RESET               "\033[0m"
#define CLR_GREEN               "\033[32m"
#define CLR_YELLOW              "\033[33m"
#define CLR_RED                 "\033[31m"
#define CLR_CYAN                "\033[36m"
#define CLR_GRAY                "\033[90m"
#define CLR_BOLD                "\033[1m"

// ============================ 传感器状态枚举 ============================

enum AlarmLevel {
    ALARM_NORMAL = 0,
    ALARM_WARNING,
    ALARM_CRITICAL
};

/* ── 传感器健康状态 ── */
enum HealthStatus { HEALTH_OK = 0, HEALTH_DEGRADED = 1, HEALTH_FAILED = 2 };

struct SensorHealth {
    float    last_val;          /* 上一次有效读数 */
    int      same_count;        /* 连续相同次数 */
    int      fail_count;        /* 连续失败次数 */
    HealthStatus status;        /* 当前健康状态 */
    const char *name;           /* 传感器名称 */
};

// ============================ 工具函数 ============================

static void time_str(char *buf, size_t n) {
    time_t t = time(NULL);
    strftime(buf, n, "%Y-%m-%d %H:%M:%S", localtime(&t));
}

static void time_short(char *buf, size_t n) {
    time_t t = time(NULL);
    strftime(buf, n, "%H:%M:%S", localtime(&t));
}

static float clamp(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

// ============================ MQ-3 传感器计算 ============================

static float read_adc(ls_adc &adc) {
    int r = adc.read_raw();
    return r < 0 ? -1.0f : (float)r * 1.8f / 4096.0f;
}

static float calc_rs(float v_mq3) {
    if (v_mq3 <= 0.01f) return 9999.0f;
    if (v_mq3 >= MQ3_VCC) return 0.0f;
    return MQ3_RL * (MQ3_VCC / v_mq3 - 1.0f);
}

static float calc_conc(float ratio) {
    if (ratio <= 0.0f) return 999.0f;
    return clamp(powf(ratio / MQ3_CURVE_A, 1.0f / MQ3_CURVE_B), 0.0f, 999.0f);
}

// ============================ MQ-3 校准 ============================

static float calibrate_mq3(ls_adc &adc) {
    FILE *f = fopen(CALIB_FILE, "r");
    float r0;
    if (f && fscanf(f, "%f", &r0) == 1 && r0 > 0) { fclose(f); return r0; }
    if (f) fclose(f);

    printf("[MQ-3] 请在洁净空气中运行，等待校准...\n");

    for (int i = 0; i < 10; i++) { read_adc(adc); usleep(200000); }

    float sum = 0; int n = 0;
    for (int i = 0; i < 30; i++) {
        float v = read_adc(adc);
        if (v > 0) {
            float rs = calc_rs(v * DIVIDER_RATIO);
            if (rs > 0 && rs < 9999) { sum += rs; n++; }
        }
        printf("\r  校准进度: %d/30", i + 1); fflush(stdout);
        usleep(200000);
    }
    printf("\n");

    r0 = (n >= 3) ? (sum / n) / MQ3_CLEAN_AIR : 50.0f;
    printf("[MQ-3] R0 = %.2f kΩ\n", r0);

    f = fopen(CALIB_FILE, "w");
    if (f) { fprintf(f, "%.2f\n", r0); fclose(f); }
    return r0;
}

// ============================ 算法引擎 ============================

/* ── 1. 卡尔曼滤波 (1D) ── */
struct Kalman1D {
    float x;    /* 状态估计 */
    float p;    /* 误差协方差 */
    bool  init;
};

static void kalman_init(Kalman1D *kf, float first_measurement) {
    kf->x = first_measurement;
    kf->p = KF_INIT_UNCERTAINTY;
    kf->init = true;
}

/* 返回滤波后的值 */
static float kalman_update(Kalman1D *kf, float measurement)
{
    if (!kf->init) { kalman_init(kf, measurement); return kf->x; }
    /* 预测: x不变, P += Q */
    kf->p += KF_PROCESS_NOISE;
    /* 更新: K = P/(P+R), x += K*(z-x), P = (1-K)*P */
    float K = kf->p / (kf->p + KF_MEASURE_NOISE);
    kf->x += K * (measurement - kf->x);
    kf->p *= (1.0f - K);
    return kf->x;
}

/* ── 2. EMA 自适应基线 ── */
struct EmaBaseline {
    float mean;     /* EMA均值 */
    float var;      /* EMA方差 */
    float sigma;    /* 估算标准差 */
    int   count;
    bool  ready;
};

static void ema_init(EmaBaseline *eb) {
    eb->mean = 0; eb->var = 0; eb->sigma = EMA_MIN_SIGMA; eb->count = 0; eb->ready = false;
}

/* 更新基线, 返回偏离基线的sigma倍数 */
static float ema_update(EmaBaseline *eb, float value)
{
    if (eb->count < 10) {
        /* 前10个样本: 直接平均初始化 */
        eb->mean += (value - eb->mean) / (eb->count + 1);
        eb->count++;
        if (eb->count == 10) {
            eb->sigma = EMA_MIN_SIGMA;
            eb->ready = true;
        }
        return 0;
    }
    /* EMA更新: 慢速跟踪环境漂移 */
    float delta = value - eb->mean;
    eb->mean += EMA_ALPHA * delta;
    eb->var   = (1.0f - EMA_ALPHA) * eb->var + EMA_ALPHA * delta * delta;
    eb->sigma = sqrtf(eb->var);
    if (eb->sigma < EMA_MIN_SIGMA) eb->sigma = EMA_MIN_SIGMA;
    /* 对大幅偏离(泄漏)降低alpha, 防止污染基线 */
    if (fabsf(delta) > EMA_SIGMA_MULT * eb->sigma && eb->count > 20) {
        eb->mean -= EMA_ALPHA * delta * 0.8f;  /* 回退80%的更新 */
    }
    eb->count++;
    return delta / eb->sigma;  /* 返回偏离sigma数 */
}

/* ── 3. 互补滤波 (MQ-3 + SGP30 融合) ── */
/* 返回融合后的乙醇浓度 */
static float complementary_fuse(float mq3_kalman, uint16_t tvoc, bool sgp30_ok)
{
    if (!sgp30_ok) return mq3_kalman;
    /* 从TVOC反推乙醇: 假设1mg/L乙醇 ≈ 100ppb TVOC (粗略估计) */
    float tvoc_ethanol = (float)tvoc * 0.01f;
    return COMP_FILTER_K * mq3_kalman + (1.0f - COMP_FILTER_K) * tvoc_ethanol;
}

/* ── 4. CUSUM 累积和检测 ── */
struct Cusum {
    float s_high;   /* 正向累积和 */
    float s_low;    /* 负向累积和 */
    bool  triggered;
};

static void cusum_init(Cusum *cs) { cs->s_high = 0; cs->s_low = 0; cs->triggered = false; }

/* 返回 true 如果累积和超过阈值 */
static bool cusum_update(Cusum *cs, float value, float baseline, float sigma)
{
    float k = CUSUM_DRIFT * sigma + 0.001f;  /* 自适应漂移参数 */
    float h = CUSUM_THRESHOLD * sigma;

    float dev_high = value - baseline - k;
    float dev_low  = baseline - value - k;

    cs->s_high = fmaxf(0, cs->s_high + dev_high);
    cs->s_low  = fmaxf(0, cs->s_low  + dev_low);

    if (cs->s_high > h) { cs->triggered = true; return true; }
    if (cs->s_low  > h) { cs->s_high = 0; cs->s_low = 0; return false; }  /* low方向不做泄漏检测 */

    /* 重置机制: 连续正常则清零 */
    if (cs->s_high < k * 3 && cs->s_low < k * 3) cs->triggered = false;
    return cs->triggered;
}

// ============================ 趋势检测 ============================

struct TrendResult {
    float slope; float avg_recent; float avg_old; bool is_rising;
};

static TrendResult detect_trend(float *buffer, int count)
{
    TrendResult r = {0};
    if (count < TREND_WINDOW) return r;
    int half = TREND_WINDOW / 2;
    float sr = 0, so = 0;
    for (int i = 0; i < half; i++)       sr += buffer[i];
    for (int i = half; i < TREND_WINDOW; i++) so += buffer[i];
    r.avg_recent = sr / half;
    r.avg_old    = so / half;
    r.slope      = (r.avg_recent - r.avg_old) / (half * INTERVAL_MS / 1000.0f);
    r.is_rising  = (r.slope > TREND_SLOPE_THRESHOLD) && (r.avg_recent > TREND_MIN_CONC);
    return r;
}

// ============================ MQ-3 温湿度补偿 ============================

static float compensate_ethanol(float ethanol_raw, float temp, float humidity, bool sht30_ok)
{
    if (!sht30_ok || ethanol_raw < 0.01f) return ethanol_raw;
    float hum_factor  = COMP_HUM_COEFF * (humidity - COMP_REF_HUM) / 100.0f;
    float temp_factor = COMP_TEMP_COEFF * (temp - COMP_REF_TEMP);
    float correction  = clamp(1.0f + hum_factor + temp_factor, 0.5f, 1.5f);
    return clamp(ethanol_raw / correction, 0.0f, 999.0f);
}

// ============================ 传感器健康监控 ============================

static void health_update(SensorHealth *h, float new_val, bool read_ok)
{
    if (!h) return;
    if (!read_ok) {
        h->fail_count++;
        if (h->fail_count >= HEALTH_FAIL_SAMPLES) h->status = HEALTH_FAILED;
    } else {
        h->fail_count = 0;
        if (fabsf(new_val - h->last_val) < 1e-6f && new_val > -1) {
            h->same_count++;
            if (h->same_count >= HEALTH_STUCK_SAMPLES) h->status = HEALTH_DEGRADED;
        } else {
            h->same_count = 0;
            if (h->status != HEALTH_FAILED) h->status = HEALTH_OK;
        }
    }
    h->last_val = new_val;
}

static const char *health_icon(HealthStatus s) {
    switch (s) {
        case HEALTH_OK:       return "\033[32m●\033[0m";
        case HEALTH_DEGRADED: return "\033[33m▲\033[0m";
        case HEALTH_FAILED:   return "\033[31m✕\033[0m";
        default:              return "?";
    }
}

// ============================ 事件快照 ============================

struct SnapEntry {
    char   ts[16];        /* 时间 */
    float  temp;          /* 温度 */
    float  hum;           /* 湿度 */
    uint16_t eco2;        /* eCO2 */
    uint16_t tvoc;        /* TVOC */
    int    flame1;        /* 火焰1 */
    int    flame2;        /* 火焰2 */
    float  ethanol;       /* 乙醇 */
    int    risk;          /* 风险分 */
};

static SnapEntry snap_buf[SNAP_BUF_SIZE];
static int        snap_idx  = 0;
static int        snap_full = 0;

/* 添加一个采样点到环形缓冲区 */
static void snap_push(const char *ts, float temp, float hum, uint16_t eco2, uint16_t tvoc,
                       int f1, int f2, float eth, int risk)
{
    SnapEntry *e = &snap_buf[snap_idx];
    strncpy(e->ts, ts, 15); e->ts[15] = '\0';
    e->temp = temp; e->hum = hum; e->eco2 = eco2; e->tvoc = tvoc;
    e->flame1 = f1; e->flame2 = f2; e->ethanol = eth; e->risk = risk;
    snap_idx = (snap_idx + 1) % SNAP_BUF_SIZE;
    if (snap_idx == 0) snap_full = 1;
}

/* 触发报警时导出快照 */
static void snap_dump(const char *alarm_cause, int alarm_num, float peak_eth_30s)
{
    mkdir(SNAPSHOT_DIR, 0755);

    char path[128];
    time_t now = time(NULL);
    struct tm *tm = localtime(&now);
    snprintf(path, sizeof(path), "%s/alarm_%02d%02d_%02d%02d%02d.txt",
             SNAPSHOT_DIR, tm->tm_mon+1, tm->tm_mday, tm->tm_hour, tm->tm_min, tm->tm_sec);

    FILE *f = fopen(path, "w");
    if (!f) return;

    fprintf(f, "══════════════════════════════════════════\n");
    fprintf(f, "  环境监测 — 报警事件快照\n");
    fprintf(f, "══════════════════════════════════════════\n");
    fprintf(f, "  触发时间: %s\n", ctime(&now));
    fprintf(f, "  报警编号: #%d\n", alarm_num);
    fprintf(f, "  报警原因: %s\n", alarm_cause);
    fprintf(f, "  30秒峰值乙醇: %.3f mg/L\n", peak_eth_30s);
    fprintf(f, "──────────────────────────────────────────\n");
    fprintf(f, "  报警前 %d 条历史记录:\n\n", snap_full ? SNAP_BUF_SIZE : snap_idx);
    fprintf(f, "  时间    | 温度℃ | 湿度%% | eCO2 | TVOC | 火 | 乙醇mg/L | 风险\n");
    fprintf(f, "  --------+-------+-------+------+------+----+----------+-----\n");

    int count = snap_full ? SNAP_BUF_SIZE : snap_idx;
    for (int i = 0; i < count; i++) {
        int idx = (snap_idx - count + i + SNAP_BUF_SIZE) % SNAP_BUF_SIZE;
        SnapEntry *e = &snap_buf[idx];
        fprintf(f, "  %s | %5.1f | %4.1f | %4u | %4u | %d%d  | %8.3f | %3d\n",
                e->ts, e->temp, e->hum, e->eco2, e->tvoc,
                e->flame1, e->flame2, e->ethanol, e->risk);
    }

    /* 简要分析 */
    if (count >= 5) {
        SnapEntry *first = &snap_buf[(snap_idx - count + SNAP_BUF_SIZE) % SNAP_BUF_SIZE];
        SnapEntry *last  = &snap_buf[(snap_idx - 1 + SNAP_BUF_SIZE) % SNAP_BUF_SIZE];
        float eth_delta = last->ethanol - first->ethanol;
        int   tvoc_delta = (int)last->tvoc - (int)first->tvoc;

        fprintf(f, "\n──────────────────────────────────────────\n");
        fprintf(f, "  变化分析 (%.0f 秒内):\n", (float)count);
        fprintf(f, "    乙醇: %.3f → %.3f (Δ%.3f mg/L)\n",
                first->ethanol, last->ethanol, eth_delta);
        fprintf(f, "    TVOC: %u → %u (Δ%d ppb)\n",
                first->tvoc, last->tvoc, tvoc_delta);
        fprintf(f, "    风险: %d → %d\n", first->risk, last->risk);

        if (eth_delta > 1.0f)
            fprintf(f, "    ⚠ 乙醇浓度急升，疑似泄漏！\n");
        if (last->flame1 || last->flame2)
            fprintf(f, "    🔥 检测到火焰信号！\n");
    }

    fprintf(f, "══════════════════════════════════════════\n");
    fclose(f);

    printf("  📸 快照已保存: %s\n", path);

    /* 清理旧快照 - 只保留最近 SNAP_FILE_MAX 个 */
    {
        char cmd[256];
        snprintf(cmd, sizeof(cmd),
                 "ls -t " SNAPSHOT_DIR "/alarm_*.txt 2>/dev/null | tail -n +%d | xargs rm -f 2>/dev/null",
                 SNAP_FILE_MAX + 1);
        system(cmd);
    }
}

// ============================ 综合风险评分 (0-100) ============================

/********************************************************************************
 * @brief   计算综合风险指数
 * @return  risk_score (0-100), *level (报警等级), *cause (原因), *xcheck (交叉验证)
 * @note    每个传感器贡献 = (当前值/报警阈值) × 权重, 钳位后求和 + 趋势/交叉加分
 ********************************************************************************/
static int calc_risk_score(float ethanol, float ethanol_raw,
                            uint16_t tvoc, uint16_t eco2,
                            bool flame1, bool flame2, float temp,
                            const TrendResult &trend, bool sgp30_ok,
                            float ema_mean, float ema_sigma, bool cusum_triggered,
                            AlarmLevel *level, const char **cause, int *xcheck)
{
    float score = 0;
    if (xcheck) *xcheck = -1;

    /* ── 火焰：非连续量，检测到即拉满 ── */
    if (flame1 && flame2) {
        /* 双传感器确认 → 直接 100 分，无需看其他传感器 */
        *level = ALARM_CRITICAL;
        *cause = "火焰(双确认)";
        if (xcheck) *xcheck = 2;
        return 100;
    }
    if (flame1 || flame2) {
        /* 单传感器触发 → 起始 85 分，其他传感器异常会继续加分 */
        score = 85;
        if (xcheck) *xcheck = 0;
    }

    /* ── 乙醇 (EMA自适应阈值) ── */
    float eth_warn, eth_alarm;
    if (ema_sigma > 0.01f && ema_mean > 0.001f) {
        eth_warn  = ema_mean + EMA_SIGMA_MULT * ema_sigma;
        eth_alarm = ema_mean + EMA_SIGMA_MULT * 2.0f * ema_sigma;
        /* 兜底: 不低于固定阈值 */
        if (eth_warn < THR_ETHANOL_WARN * 0.5f)  eth_warn = THR_ETHANOL_WARN * 0.5f;
        if (eth_alarm < THR_ETHANOL_ALARM * 0.5f) eth_alarm = THR_ETHANOL_ALARM * 0.5f;
    } else {
        eth_warn = THR_ETHANOL_WARN; eth_alarm = THR_ETHANOL_ALARM;
    }

    if (ethanol >= eth_alarm) {
        score += RISK_W_MQ3;
    } else if (ethanol >= eth_warn) {
        score += RISK_W_MQ3 * (0.5f + 0.5f * (ethanol - eth_warn) / (eth_alarm - eth_warn + 0.001f));
    } else if (ethanol > eth_warn * 0.3f) {
        score += RISK_W_MQ3 * 0.1f;
    }

    /* ── TVOC ── */
    float tvoc_warn = THR_TVOC_WARN, tvoc_alarm = THR_TVOC_ALARM;
    if (sgp30_ok) {
        if (tvoc >= tvoc_alarm) score += RISK_W_TVOC;
        else if (tvoc >= tvoc_warn) score += RISK_W_TVOC * 0.5f;
        else if (tvoc > tvoc_warn * 0.3f) score += RISK_W_TVOC * 0.1f;
    }

    /* ── eCO2 ── */
    if (sgp30_ok) {
        if (eco2 >= THR_ECO2_ALARM) score += RISK_W_ECO2;
        else if (eco2 >= THR_ECO2_WARN) score += RISK_W_ECO2 * 0.5f;
    }

    /* ── 温度 ── */
    if (temp >= THR_TEMP_HIGH) score += RISK_W_TEMP;
    else if (temp >= 40) score += RISK_W_TEMP * 0.5f;

    /* ── 交叉验证加分 ── */
    bool eth_high = (ethanol >= eth_warn);
    bool tvoc_high = sgp30_ok && (tvoc >= tvoc_warn);
    if (eth_high && tvoc_high) {
        score += RISK_BONUS_XCHECK;
        if (xcheck) *xcheck = 2;
    } else if (eth_high && !tvoc_high) {
        if (xcheck) *xcheck = 0;
        if (trend.is_rising) { score += RISK_BONUS_XCHECK * 0.5f; if (xcheck) *xcheck = 1; }
    } else if (!eth_high && tvoc_high && sgp30_ok) {
        if (xcheck) *xcheck = 1;
    }

    /* ── 趋势加分 ── */
    if (trend.is_rising) score += RISK_BONUS_TREND;

    /* ── CUSUM 累积和加分 ── */
    if (cusum_triggered) score += CUSUM_BONUS;

    /* ── 钳位 ── */
    int risk = (int)(score + 0.5f);
    if (risk > 100) risk = 100;
    if (risk < 0)   risk = 0;

    /* ── 映射到等级 ── */
    if (risk <= RISK_SAFE)       *level = ALARM_NORMAL;
    else if (risk <= RISK_CAUTION) *level = ALARM_NORMAL;
    else if (risk <= RISK_WARNING) *level = ALARM_WARNING;
    else if (risk <= RISK_SEVERE)  *level = ALARM_CRITICAL;
    else                           *level = ALARM_CRITICAL;

    /* ── 原因 ── */
    if (eth_high && tvoc_high) *cause = "乙醇+TVOC(双重确认)";
    else if (cusum_triggered)       *cause = "CUSUM累积异常(早期)";
    else if (eth_high && trend.is_rising) *cause = "乙醇偏高+趋势上升";
    else if (eth_high)              *cause = "乙醇偏高";
    else if (trend.is_rising)       *cause = "趋势上升(预警)";
    else if (tvoc_high)             *cause = "TVOC偏高";
    else if (eco2 >= THR_ECO2_WARN && sgp30_ok) *cause = "eCO2偏高";
    else if (temp >= 40)            *cause = "温度偏高";
    else                            *cause = "正常";

    return risk;
}

// ============================ CSV 日志写入 ============================

static void log_csv(const char *ts, float temp, float hum,
                     uint16_t eco2, uint16_t tvoc,
                     int flame1, int flame2,
                     float ethanol, float ethanol_raw, float voltage,
                     int level, int crosscheck, bool trend_rising)
{
    static bool header_written = false;
    FILE *f = fopen(LOG_CSV, "a");
    if (!f) return;

    if (!header_written) {
        fprintf(f, "timestamp,temp_c,humidity_pct,eco2_ppm,tvoc_ppb,"
                   "flame1,flame2,ethanol_mgl,ethanol_raw_mgl,voltage_v,"
                   "alarm_level,crosscheck,trend_rising\n");
        header_written = true;
    }

    fprintf(f, "%s,%.2f,%.1f,%u,%u,%d,%d,%.3f,%.3f,%.2f,%d,%d,%d\n",
            ts, temp, hum, eco2, tvoc, flame1, flame2,
            ethanol, ethanol_raw, voltage,
            level, crosscheck, trend_rising ? 1 : 0);
    fclose(f);
}

// ============================ 报警文件 ============================

static void write_alarm_file(int level, const char *ts, const char *cause)
{
    FILE *f = fopen(ALARM_FILE, "w");
    if (!f) return;
    const char *str;
    switch (level) {
        case ALARM_CRITICAL: str = "CRITICAL"; break;
        case ALARM_WARNING:  str = "WARNING";  break;
        default:             str = "NORMAL";   break;
    }
    fprintf(f, "%d|%s|%s", level, str, cause ? cause : "");
    fclose(f);
}

// ============================ 主函数 ============================

int main()
{
    printf("\n");
    printf(CLR_BOLD "═══════════════════════════════════════════════════════════\n" CLR_RESET);
    printf(CLR_BOLD "       五传感器综合环境监测系统  v3.1\n" CLR_RESET);
    printf(CLR_BOLD "═══════════════════════════════════════════════════════════\n" CLR_RESET);
    printf("  SHT30 (温湿度)    I2C-5, 0x44    PIN_50/51\n");
    printf("  SGP30 (空气质量)   I2C-5, 0x58    PIN_50/51\n");
    printf("  火焰×2 (红外)      GPIO           PIN_72/73\n");
    printf("  MQ-3  (乙醇)       ADC_CH0        PIN_75 (DO)\n");
    printf("  报警灯泡           GPIO           PIN_74\n");
    printf(CLR_GRAY "  间隔:%dms 窗口:%d 防抖:%d/%d  趋势:%d样本 交叉验证:开\n" CLR_RESET,
           INTERVAL_MS, WINDOW_SIZE, CONFIRM_CNT, CLEAR_CNT, TREND_WINDOW);
    printf("═══════════════════════════════════════════════════════════\n\n");

    // ============================ 硬件初始化 ============================

    /* SHT30 */
    lq_sht30 sht30;
    float temp_c = 0, humidity = 0;
    bool sht30_ok = false;

    /* SGP30 */
    lq_sgp30 sgp30;
    uint16_t eco2 = 0, tvoc = 0;
    bool sgp30_ok = false;
    bool sgp30_ready = false;

    /* MQ-3 */
    ls_gpio  mq3_do(MQ3_DO_PIN, GPIO_MODE_IN);
    ls_adc   adc(MQ3_ADC_CH);

    /* 火焰传感器 */
    ls_gpio  flame1(FLAME1_DO_PIN, GPIO_MODE_IN);
    ls_gpio  flame2(FLAME2_DO_PIN, GPIO_MODE_IN);

    /* 报警灯泡 */
    ls_gpio  bulb(BULB_PIN, GPIO_MODE_OUT);
    bulb.gpio_level_set(GPIO_LOW);  /* 初始化为灭 */

    /* SHT30 简单连通性检查 */
    {
        float t, h;
        if (sht30.read_sensor(&t, &h) == 0) {
            sht30_ok = true;
            printf("[SHT30] 已连接  |  温度: %.1f℃  |  湿度: %.1f%%RH\n", t, h);
        } else {
            printf(CLR_YELLOW "[SHT30] 未检测到传感器 (继续运行)\n" CLR_RESET);
        }
    }

    /* SGP30 初始化 */
    if (sgp30.init() == 0) {
        sgp30_ok = true;
        printf("[SGP30] 已连接  |  预热中... (约需 15 秒)\n");

        /* 如果 SHT30 可用，设置湿度补偿 */
        if (sht30_ok) {
            sgp30.set_humidity_compensation(temp_c, humidity);
            printf("[SGP30] 已应用湿度补偿\n");
        }
    } else {
        printf(CLR_YELLOW "[SGP30] 未检测到传感器 (继续运行)\n" CLR_RESET);
    }

    /* MQ-3 校准 */
    float r0 = calibrate_mq3(adc);

    printf("\n");

    // ============================ 算法引擎初始化 ============================

    /* 卡尔曼滤波器 */
    Kalman1D kf_ethanol = {0};

    /* EMA 自适应基线 */
    EmaBaseline ema_bl;
    ema_init(&ema_bl);
    float ema_sigma  = EMA_MIN_SIGMA;
    float ema_mean   = 0;
    bool  ema_ready  = false;

    /* CUSUM 累积和检测器 */
    Cusum cusum;
    cusum_init(&cusum);

    printf("[算法] 卡尔曼滤波 + EMA基线 + 互补融合 + CUSUM 已就绪\n");

    // ============================ MQTT 通信初始化 ============================

    lq_mqtt mqtt("192.168.43.36", 1883, "board_2k0301");
    bool mqtt_ok = mqtt.connect();
    if (mqtt_ok) {
        printf("[MQTT] 已连接到 2K1000LA Broker\n");

        /* 设置命令回调 */
        mqtt.set_command_callback([](const CommandParams &cmd, bool *exec_ok,
                                      char *ack_msg, size_t ack_size) {
            switch (cmd.cmd) {
            case CMD_FAN_CONTROL:
                /* TODO: 接入 TB6612 电机驱动后实现 */
                snprintf(ack_msg, ack_size, "fan_control %s (未接硬件,命令已记录)",
                         cmd.fan_on ? "on" : "off");
                *exec_ok = true;  /* 暂时接受,硬件就绪后真正执行 */
                break;
            case CMD_BUZZER_CONTROL:
                /* TODO: 接入蜂鸣器后实现 */
                snprintf(ack_msg, ack_size, "buzzer %s (未接硬件)", cmd.buzzer_on ? "on" : "off");
                *exec_ok = true;
                break;
            case CMD_ALARM_LIGHT:
                /* 当前使用单色灯泡 PIN_74, 后续升级三色灯 */
                if (strcmp(cmd.light_color, "red") == 0 || strcmp(cmd.light_color, "off") != 0) {
                    /* 暂时用现有灯泡响应 */
                    snprintf(ack_msg, ack_size, "alarm_light %s (使用PIN_74单色灯)", cmd.light_color);
                    *exec_ok = true;
                } else {
                    snprintf(ack_msg, ack_size, "alarm_light accepted");
                    *exec_ok = true;
                }
                break;
            case CMD_DEVICE_RESET:
                snprintf(ack_msg, ack_size, "reset %s acknowledged", cmd.reset_target);
                *exec_ok = true;
                break;
            default:
                snprintf(ack_msg, ack_size, "unknown command");
                *exec_ok = false;
                /* 上报错误 */
                break;
            }
            printf("  [MQTT] 收到命令: %s → %s\n",
                   cmd.cmd == CMD_UNKNOWN ? "未知" : cmd.raw_json,
                   *exec_ok ? "ACK OK" : "ACK FAIL");
        });
    } else {
        printf(CLR_YELLOW "[MQTT] 无法连接 Broker, 仅本地模式运行\n" CLR_RESET);
    }

    // ============================ 传感器健康追踪 ============================

    SensorHealth h_mq3  = {0, 0, 0, HEALTH_OK, "MQ-3"};
    SensorHealth h_sht30= {0, 0, 0, HEALTH_OK, "SHT30"};
    SensorHealth h_sgp30= {0, 0, 0, HEALTH_OK, "SGP30"};
    SensorHealth h_flame1={0, 0, 0, HEALTH_OK, "火焰1"};
    SensorHealth h_flame2={0, 0, 0, HEALTH_OK, "火焰2"};

    // ============================ 状态变量 ============================

    int risk_score   = 0;              /* 综合风险指数 0-100 */
    int last_risk    = 0;
    int alarm_state  = ALARM_NORMAL;
    int last_alarm   = ALARM_NORMAL;
    int confirm      = 0;
    int clear_cnt    = 0;
    int alarm_count  = 0;

    /* 趋势检测 */
    float trend_buf[TREND_WINDOW] = {0};
    int   trend_count = 0;

    float peak_ethanol = 0, peak_voltage = 0;

    /* 交叉验证 */
    int crosscheck = -1;

    char ts[64], ts_short[16];

    // ============================ 表头 ============================

    printf("  时间     | 温度℃ | 湿度%% | eCO2  | TVOC | 火1 | 火2 | 乙醇mg/L | 风险 | 状态\n");
    printf("  ---------+-------+-------+-------+------+-----+-----+----------+------+---------\n");

    // ============================ 启动日志 ============================

    time_str(ts, sizeof(ts));
    FILE *af = fopen(ALARM_FILE, "w");
    if (af) { fprintf(af, "0|NORMAL|%s", ts); fclose(af); }

    // ============================ 主循环 ============================

    while (ls_system_running.load()) {

        time_str(ts, sizeof(ts));
        time_short(ts_short, sizeof(ts_short));

        // ======================== 1. 读取 SHT30 ========================

        if (sht30_ok) {
            float t, h;
            if (sht30.read_sensor(&t, &h) == 0) {
                temp_c   = t;
                humidity = h;
            }
        }

        // ======================== 2. 读取 SGP30 ========================

        if (sgp30_ok) {
            if (!sgp30_ready) {
                sgp30_ready = sgp30.is_ready();
            }
            if (sgp30_ready) {
                sgp30.read(&eco2, &tvoc);
                /* 定期更新湿度补偿 */
                if (sht30_ok) {
                    static int comp_tick = 0;
                    if (++comp_tick % 60 == 0) {  /* 每 60 秒更新一次 */
                        sgp30.set_humidity_compensation(temp_c, humidity);
                    }
                }
            }
        }

        // ======================== 3. 读取火焰传感器 ========================

        /* LM393 开漏输出: LOW = 检测到火焰, HIGH = 正常 */
        bool flame1_alarm = (flame1.gpio_level_get() == GPIO_LOW);
        bool flame2_alarm = (flame2.gpio_level_get() == GPIO_LOW);

        // ======================== 4. 读取 MQ-3 (滑动平均) ========================

        float adc_sum = 0; int adc_n = 0;
        for (int i = 0; i < WINDOW_SIZE; i++) {
            float v = read_adc(adc);
            if (v >= 0) { adc_sum += v; adc_n++; }
            if (i < WINDOW_SIZE - 1) usleep(INTERVAL_MS * 1000 / WINDOW_SIZE);
        }

        float adc_v  = (adc_n > 0) ? (adc_sum / adc_n) : 0;
        float v_mq3  = adc_v * DIVIDER_RATIO;
        float rs     = calc_rs(v_mq3);
        float ratio  = r0 > 0 ? rs / r0 : 0;
        float ethanol_raw = calc_conc(ratio);           /* 原始乙醇浓度 */

        /* ── 算法管线: 卡尔曼滤波 → EMA基线 → 互补融合 → CUSUM ── */
        float ethanol_kf = kalman_update(&kf_ethanol, ethanol_raw);  /* 1.卡尔曼去噪 */
        float sigma_dev  = ema_update(&ema_bl, ethanol_kf);          /* 2.EMA自适应基线 */
        ema_sigma = ema_bl.sigma;
        ema_mean  = ema_bl.mean;
        ema_ready = ema_bl.ready;

        /* 3.互补滤波融合 (卡尔曼值 + SGP30 TVOC) */
        float ethanol_fused = complementary_fuse(ethanol_kf, tvoc, sgp30_ok && sgp30_ready);

        /* 4.CUSUM 累积和检测 */
        bool cusum_alarm = cusum_update(&cusum, ethanol_fused, ema_bl.mean, ema_bl.sigma);

        /* ── 温湿度补偿 ── */
        float ethanol = compensate_ethanol(ethanol_fused, temp_c, humidity, sht30_ok);

        /* ── 趋势检测 (基于融合值) ── */
        memmove(trend_buf + 1, trend_buf, (TREND_WINDOW - 1) * sizeof(float));
        trend_buf[0] = ethanol;
        if (trend_count < TREND_WINDOW) trend_count++;
        TrendResult trend = detect_trend(trend_buf, trend_count);

        if (ethanol > peak_ethanol) peak_ethanol = ethanol;
        if (v_mq3   > peak_voltage) peak_voltage = v_mq3;

        bool mq3_digital = (mq3_do.gpio_level_get() == GPIO_HIGH);

        /* ── 快照：每周期记录一个采样点 ── */
        snap_push(ts_short, temp_c, humidity, eco2, tvoc,
                  flame1_alarm ? 1 : 0, flame2_alarm ? 1 : 0,
                  ethanol, risk_score);

        // ======================== 5. 传感器健康监控 ========================

        health_update(&h_mq3, ethanol, true);
        health_update(&h_sht30, temp_c, sht30_ok);
        health_update(&h_sgp30, (float)tvoc, sgp30_ok && sgp30_ready);
        health_update(&h_flame1, flame1_alarm ? 1.0f : 0.0f, true);
        health_update(&h_flame2, flame2_alarm ? 1.0f : 0.0f, true);

        // ======================== 7. 综合风险评分 ========================

        AlarmLevel new_level;
        const char *cause = "";
        risk_score = calc_risk_score(ethanol, ethanol_raw,
                                      tvoc, eco2,
                                      flame1_alarm, flame2_alarm, temp_c,
                                      trend, sgp30_ok && sgp30_ready,
                                      ema_mean, ema_sigma, cusum_alarm,
                                      &new_level, &cause, &crosscheck);

        /* MQ-3 数字报警高优先级 */
        if (mq3_digital && new_level < ALARM_CRITICAL) {
            new_level = ALARM_CRITICAL;
            risk_score = (risk_score < 80) ? 85 : risk_score;
        }

        /* 防抖状态机 */
        if (new_level > alarm_state) {
            confirm++;
            if (confirm >= CONFIRM_CNT) { alarm_state = new_level; clear_cnt = 0; }
        } else if (new_level < alarm_state) {
            clear_cnt++;
            if (clear_cnt >= CLEAR_CNT) { alarm_state = new_level; confirm = 0; }
        } else { confirm = 0; clear_cnt = 0; }

        // ======================== 8. 状态变化处理 ========================

        if (alarm_state != last_alarm) {
            const char *clr, *txt;

            switch (alarm_state) {
            case ALARM_CRITICAL:
                alarm_count++;
                bulb.gpio_level_set(GPIO_HIGH);
                clr = CLR_RED; txt = "‼报警";

                /* 导出事件快照 */
                snap_dump(cause, alarm_count, peak_ethanol);

                { FILE *ef = fopen("/home/root/alarm_event.txt", "a");
                  if (ef) { fprintf(ef, "[%s] ALARM #%d: %s | 风险=%d 乙醇=%.3f TVOC=%u T=%.1f\n",
                                    ts, alarm_count, cause, risk_score, ethanol, tvoc, temp_c);
                  fclose(ef); }
                }
                break;
            case ALARM_WARNING:
                clr = CLR_YELLOW; txt = "⚠预警";
                break;
            default:
                bulb.gpio_level_set(GPIO_LOW);
                clr = CLR_GREEN; txt = "✓恢复";
                { FILE *ef = fopen("/home/root/alarm_event.txt", "a");
                  if (ef) { fprintf(ef, "[%s] 恢复 | 峰值乙醇=%.3f mg/L | 风险=%d\n",
                                    ts, peak_ethanol, risk_score);
                  fclose(ef); }
                }
                peak_ethanol = 0; peak_voltage = 0;
                break;
            }

            printf("  %s | " CLR_BOLD "%s%s" CLR_RESET "   [%d] %s\n",
                   ts_short, clr, txt, risk_score, cause);
            write_alarm_file(alarm_state, ts, cause);
        }
        last_alarm = alarm_state;

        // ======================== 9. 周期显示 + 风险评分 + 健康图标 ========================

        {
            /* 风险评分颜色 */
            const char *rclr;
            if (risk_score <= RISK_SAFE)       rclr = CLR_GREEN;
            else if (risk_score <= RISK_CAUTION) rclr = CLR_CYAN;
            else if (risk_score <= RISK_WARNING) rclr = CLR_YELLOW;
            else if (risk_score <= RISK_SEVERE)  rclr = CLR_RED;
            else                                 rclr = CLR_RED CLR_BOLD;

            /* 状态 */
            const char *clr, *sym;
            switch (alarm_state) {
                case ALARM_CRITICAL: clr = CLR_RED;    sym = "‼报警"; break;
                case ALARM_WARNING:  clr = CLR_YELLOW; sym = "⚠预警"; break;
                default:             clr = CLR_GREEN;  sym = "✓正常"; break;
            }

            /* SGP30 预热 */
            char eco2_str[8], tvoc_str[8];
            if (!sgp30_ok) { snprintf(eco2_str, 8, "  --  "); snprintf(tvoc_str, 8, "  -- "); }
            else if (!sgp30_ready) { snprintf(eco2_str, 8, " 预热 "); snprintf(tvoc_str, 8, " 预热 "); }
            else { snprintf(eco2_str, 8, "%5u", eco2); snprintf(tvoc_str, 8, "%4u", tvoc); }

            /* SHT30 */
            char temp_str[8], hum_str[8];
            if (sht30_ok) { snprintf(temp_str, 8, "%5.1f", temp_c); snprintf(hum_str, 8, "%4.1f", humidity); }
            else { snprintf(temp_str, 8, "  --  "); snprintf(hum_str, 8, "  -- "); }

            /* 趋势 + 基线状态 */
            const char *ema_status = ema_ready ? CLR_GREEN "Ⓔ" CLR_RESET : CLR_YELLOW "Ⓔ" CLR_RESET;
            const char *cusum_indicator = cusum_alarm ? CLR_RED "∑!" CLR_RESET : "";
            const char *trend_indicator = trend.is_rising ? CLR_RED "↗" CLR_RESET : " ";
            const char *comp_indicator = (sht30_ok && ethanol_raw > 0.01f) ? "*" : " ";

            printf("  %s | %s | %s | %s | %s | %s%d%s | %s%d%s |%s%s%s %5.3f | %s%3d" CLR_RESET " %s %s%s" CLR_RESET "\n",
                   ts_short, temp_str, hum_str, eco2_str, tvoc_str,
                   health_icon(h_flame1.status), flame1_alarm ? 1 : 0, CLR_RESET,
                   health_icon(h_flame2.status), flame2_alarm ? 1 : 0, CLR_RESET,
                   comp_indicator, trend_indicator, cusum_indicator, ethanol,
                   rclr, risk_score, ema_status, clr, sym);
        }

        /* 定期健康报告 */
        {
            static int health_tick = 0;
            if (++health_tick % HEALTH_CHECK_INTERVAL == 0) {
                bool any_issue = (h_mq3.status > HEALTH_OK || h_sht30.status > HEALTH_OK ||
                                  h_sgp30.status > HEALTH_OK || h_flame1.status > HEALTH_OK ||
                                  h_flame2.status > HEALTH_OK);
                if (any_issue) {
                    printf("  " CLR_GRAY "传感器健康: %s%s %s%s %s%s %s%s %s%s" CLR_RESET "\n",
                           health_icon(h_mq3.status), h_mq3.name,
                           health_icon(h_sht30.status), h_sht30.name,
                           health_icon(h_sgp30.status), h_sgp30.name,
                           health_icon(h_flame1.status), h_flame1.name,
                           health_icon(h_flame2.status), h_flame2.name);
                }
            }
        }

        // ======================== 10. CSV 日志 ========================

        log_csv(ts, temp_c, humidity, eco2, tvoc,
                flame1_alarm ? 1 : 0, flame2_alarm ? 1 : 0,
                ethanol, ethanol_raw, v_mq3, alarm_state, crosscheck, trend.is_rising);

        // ======================== 11. MQTT 数据上报 + 心跳 + 错误 ========================

        if (mqtt_ok) {
            mqtt.spin();  /* 处理接收消息 (非阻塞, 100ms) */

            /* 构建传感器 JSON payload */
            char sensor_json[1024];
            snprintf(sensor_json, sizeof(sensor_json),
                "{\"device_id\":\"board_2k0301\","
                "\"timestamp\":\"%s\","
                "\"temperature\":%.1f,\"humidity\":%.1f,"
                "\"tvoc\":%u,\"eco2\":%u,"
                "\"mq3_value\":%.3f,"
                "\"flame_detected\":%s,"
                "\"risk_score\":%d}",
                ts,
                sht30_ok ? (double)temp_c : -999.0,
                sht30_ok ? (double)humidity : -1.0,
                (sgp30_ok && sgp30_ready) ? tvoc : 0,
                (sgp30_ok && sgp30_ready) ? eco2 : 0,
                (double)ethanol,
                (flame1_alarm || flame2_alarm) ? "true" : "false",
                risk_score);
            mqtt.publish_sensor(sensor_json);

            /* 心跳: 每 2 秒一次 */
            {
                static int hb_tick = 0;
                if (++hb_tick % 2 == 0) {
                    long uptime = mqtt.uptime_sec();
                    bool sensor_ok = (h_mq3.status != HEALTH_FAILED &&
                                      h_sht30.status != HEALTH_FAILED &&
                                      h_sgp30.status != HEALTH_FAILED);
                    mqtt.publish_heartbeat(hb_tick / 2, uptime * 1000,
                                           sensor_ok, true, NULL);
                }
            }

            /* 错误上报: 传感器故障时触发 */
            {
                static bool last_mq3_fail = false, last_sht30_fail = false, last_sgp30_fail = false;
                bool mq3_fail  = (h_mq3.status == HEALTH_FAILED);
                bool sht30_fail = (h_sht30.status == HEALTH_FAILED);
                bool sgp30_fail = (h_sgp30.status == HEALTH_FAILED);

                if (mq3_fail && !last_mq3_fail)
                    mqtt.publish_error(0, "SENSOR_ERROR", "MQ-3 read failure");
                if (sht30_fail && !last_sht30_fail)
                    mqtt.publish_error(0, "SENSOR_ERROR", "SHT30 read failure");
                if (sgp30_fail && !last_sgp30_fail)
                    mqtt.publish_error(0, "SENSOR_ERROR", "SGP30 read failure");

                last_mq3_fail = mq3_fail; last_sht30_fail = sht30_fail; last_sgp30_fail = sgp30_fail;
            }
        }

        // ======================== 12. 等待下一个周期 ========================

        usleep(INTERVAL_MS * 1000);
    }

    // ============================ 退出清理 ============================

    /* 断开 MQTT */
    if (mqtt_ok) {
        printf("[MQTT] 正在断开...\n");
        mqtt.disconnect();
    }

    bulb.gpio_level_set(GPIO_LOW);

    time_str(ts, sizeof(ts));
    FILE *ef = fopen("/home/root/alarm_event.txt", "a");
    if (ef) { fprintf(ef, "--- 系统退出 (累计报警 %d 次) [%s] ---\n",
                      alarm_count, ts); fclose(ef); }

    write_alarm_file(0, ts, "");

    /* SGP30 退出前保存基线 */
    if (sgp30_ok && sgp30_ready) {
        printf("[SGP30] 正在保存基线...\n");
        sgp30.save_baseline();
    }

    printf(CLR_BOLD "\n═══════════════════════════════════════════════════════════\n" CLR_RESET);
    printf("  系统安全退出  |  运行期间累计报警: %d 次\n", alarm_count);
    printf(CLR_BOLD "═══════════════════════════════════════════════════════════\n" CLR_RESET);

    return 0;
}
