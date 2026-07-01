# 密闭空间智能安全监护仪：仓库建立与 AI Agent 开发工作流

本文档用于指导本项目的仓库初始化、目录规划、Windows + Linux VM + 龙芯开发板的 SSH 开发流程，以及 Codex / Claude Code 等 AI Agent 的协作方式。

---

## 1. 项目开发模式

本项目推荐采用三层开发模式：

```text
Windows 开发主机
  ├─ VSCode / Claude Code / Codex
  ├─ Git / 文档 / 项目管理
  └─ 通过 SSH 控制编译与部署
        ↓
Ubuntu Linux 虚拟机
  ├─ LoongArch 交叉编译工具链
  ├─ CMake / Make / Python 环境
  ├─ 编译 2K1000LA 与 2K0301 相关程序
  └─ 通过 SCP / rsync 部署到开发板
        ↓
龙芯开发板
  ├─ 2K1000LA：运行 HMI、视觉、语音、云端通信等主控程序
  └─ 2K0301：运行传感器采集与执行控制程序
```

核心原则：

> Windows 负责写代码和调用 AI Agent，Linux VM 负责编译，龙芯板只负责运行和验证。

不要直接在龙芯板上长期写代码，也不要把板子当作主要开发环境。

---

## 2. 推荐仓库结构

建议仓库命名：

```text
SafetyGuardian-Loongson
```

推荐目录结构：

```text
SafetyGuardian-Loongson/
│
├── AGENTS.md                         # 给 AI Agent 的最高优先级开发规范
├── PROJECT_CONTEXT.md                # 项目背景、硬件、模块、当前进度
├── README.md                         # 项目总说明
├── CHANGELOG.md                      # 开发记录
├── TODO.md                           # 当前任务清单
│
├── docs/                             # 设计文档、答辩材料、方案总结
│   ├── architecture/                 # 系统架构文档
│   ├── hardware/                     # 硬件资料与连接说明
│   ├── software/                     # 软件设计文档
│   ├── test_plan/                    # 测试计划
│   └── competition/                  # 比赛申报、PPT、论文素材
│
├── protocol/                         # 统一通信协议与 JSON 数据格式
│   ├── sensor_packet.schema.json
│   ├── risk_packet.schema.json
│   ├── cloud_event.schema.json
│   └── judge_result.schema.json
│
├── firmware_2k301/                   # 2K0301 采集与执行控制程序
│   ├── src/
│   ├── include/
│   ├── tests/
│   ├── CMakeLists.txt
│   └── README.md
│
├── app_2k1000la/                     # 2K1000LA 主控应用
│   ├── src/
│   ├── include/
│   ├── tests/
│   ├── CMakeLists.txt
│   └── README.md
│
├── qt_hmi/                           # HMI 显示界面
│   ├── src/
│   ├── ui/
│   ├── resources/
│   ├── tests/
│   └── README.md
│
├── vision/                           # 摄像头与视觉识别模块
│   ├── src/
│   ├── models/
│   ├── test_images/
│   └── README.md
│
├── voice/                            # 语音唤醒、识别、播报模块
│   ├── src/
│   ├── wakeword/
│   ├── asr/
│   ├── tts/
│   └── README.md
│
├── safecloud/                        # 云端 SafeCloud 服务
│   ├── app/
│   ├── api/
│   ├── llm_clients/
│   ├── judge/
│   ├── reports/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
│
├── scripts/                          # 自动化脚本
│   ├── env/
│   │   ├── setup_vm.sh
│   │   └── check_ssh.sh
│   ├── build/
│   │   ├── build_2k301.sh
│   │   ├── build_2k1000la.sh
│   │   └── build_all.sh
│   ├── deploy/
│   │   ├── deploy_2k301.sh
│   │   ├── deploy_2k1000la.sh
│   │   └── deploy_all.sh
│   ├── run/
│   │   ├── run_2k301.sh
│   │   ├── run_2k1000la.sh
│   │   └── run_safecloud.sh
│   └── logs/
│       ├── fetch_2k301_logs.sh
│       ├── fetch_2k1000la_logs.sh
│       └── fetch_all_logs.sh
│
├── tests/                            # 系统级测试
│   ├── mock_data/
│   ├── integration/
│   └── scenarios/
│
└── tools/                            # 辅助工具
    ├── packet_sender/
    ├── mock_sensor/
    ├── mock_cloud/
    └── log_viewer/
```

---

## 3. 设备角色定义

### 3.1 Windows 主机

Windows 主机是开发中心，负责：

- 使用 VSCode / Claude Code / Codex 修改代码；
- 管理 Git 仓库；
- 编写文档、PPT、报告；
- 通过 SSH 连接 Linux VM 与龙芯开发板；
- 调用自动化脚本完成编译、部署、运行和日志抓取。

### 3.2 Ubuntu Linux VM

Linux VM 是本地编译服务器，负责：

- 安装 LoongArch 工具链；
- 编译 C / C++ / Qt / OpenCV 相关程序；
- 编译完成后通过 SCP / rsync 发送到开发板；
- 可运行 SafeCloud 服务进行本地测试。

推荐系统：

```text
Ubuntu 22.04 LTS
```

推荐虚拟机配置：

```text
CPU：8 核或以上
内存：16 GB 或以上
硬盘：80 GB 或以上
网络：桥接模式优先
```

### 3.3 龙芯 2K1000LA

2K1000LA 是现场智能仪器主控，负责：

- HMI 显示屏；
- 摄像头与视觉识别；
- 语音交互；
- 本地规则判断；
- 与 2K0301 通信；
- 与 SafeCloud 通信；
- 显示 LLM 仲裁结果和安全报告。

### 3.4 龙芯 2K0301

2K0301 是采集与执行控制节点，负责：

- SHT 温湿度采集；
- SGP30 TVOC / eCO₂ 采集；
- MQ-3 挥发物强度采集；
- FC-01 火焰状态采集；
- 三色灯控制；
- 蜂鸣器控制；
- TB6612 + 直流电机模拟排风；
- 本地安全兜底。

---

## 4. SSH 工作流

### 4.1 网络结构

比赛演示阶段推荐：

```text
手机热点 / 便携路由器
    ├─ Windows 主机
    ├─ Ubuntu Linux VM
    ├─ 龙芯 2K1000LA
    └─ 龙芯 2K0301
```

Linux VM 推荐桥接网络，使其与 Windows、龙芯板处于同一局域网。

### 4.2 建议配置 SSH Host

在 Windows 的 SSH 配置文件中添加：

```text
# Windows: C:\Users\<你的用户名>\.ssh\config

Host vm-build
    HostName 192.168.x.x
    User your_vm_user
    Port 22

Host board-2k1000la
    HostName 192.168.x.x
    User root
    Port 22

Host board-2k301
    HostName 192.168.x.x
    User root
    Port 22
```

配置完成后可直接使用：

```bash
ssh vm-build
ssh board-2k1000la
ssh board-2k301
```

### 4.3 推荐使用 SSH Key

在 Windows 上生成密钥：

```bash
ssh-keygen -t ed25519 -C "safety-guardian-dev"
```

把公钥复制到 Linux VM 和两块开发板：

```bash
ssh-copy-id vm-build
ssh-copy-id board-2k1000la
ssh-copy-id board-2k301
```

如果 Windows 没有 `ssh-copy-id`，可以手动把 `~/.ssh/id_ed25519.pub` 内容追加到远端的：

```text
~/.ssh/authorized_keys
```

---

## 5. 标准开发流水线

### 5.1 日常开发流程

```text
1. Windows 上使用 Claude Code / Codex 修改工程代码
2. Git 保存修改
3. SSH 到 Linux VM 编译
4. 编译产物通过 SCP / rsync 发送到龙芯板
5. SSH 到龙芯板运行程序
6. 抓取日志
7. 根据日志继续让 Agent 修改
```

### 5.2 命令示例

从 Windows 触发 Linux VM 编译：

```bash
ssh vm-build "cd ~/SafetyGuardian-Loongson && ./scripts/build/build_all.sh"
```

从 Linux VM 部署到 2K1000LA：

```bash
ssh vm-build "cd ~/SafetyGuardian-Loongson && ./scripts/deploy/deploy_2k1000la.sh"
```

远程运行 2K1000LA 程序：

```bash
ssh board-2k1000la "cd ~/safety_guardian && ./run_app.sh"
```

抓取日志：

```bash
ssh board-2k1000la "tail -n 100 ~/safety_guardian/logs/app.log"
```

---

## 6. 自动化脚本规划

### 6.1 一键编译脚本

路径：

```text
scripts/build/build_all.sh
```

目标：

- 编译 2K0301 程序；
- 编译 2K1000LA 主控程序；
- 编译 / 打包 HMI；
- 检查 SafeCloud Python 依赖；
- 输出所有构建产物路径。

### 6.2 一键部署脚本

路径：

```text
scripts/deploy/deploy_all.sh
```

目标：

- 把 2K1000LA 程序发送到 2K1000LA；
- 把 2K0301 程序发送到 2K0301；
- 同步配置文件；
- 同步协议文件；
- 不覆盖本地日志。

### 6.3 一键运行脚本

路径：

```text
scripts/run/run_2k1000la.sh
scripts/run/run_2k301.sh
scripts/run/run_safecloud.sh
```

目标：

- 启动目标程序；
- 打印启动状态；
- 记录日志；
- 程序退出时返回退出码。

### 6.4 一键日志脚本

路径：

```text
scripts/logs/fetch_all_logs.sh
```

目标：

- 拉取 2K1000LA 日志；
- 拉取 2K0301 日志；
- 拉取 SafeCloud 日志；
- 保存到 Windows 或 VM 的 `logs/archive/` 目录。

---

## 7. Agent 开发原则

AI Agent 必须遵守以下原则：

### 7.1 禁止直接破坏系统结构

Agent 不得随意重命名顶层目录，不得随意移动模块边界。

### 7.2 当前测哪个模块，其它模块使用模拟数据

例如：

- 测执行层时，不依赖真实传感器；
- 测 HMI 时，不依赖真实云端；
- 测云端时，不依赖真实开发板；
- 测语音时，可先用文字指令替代语音识别结果。

### 7.3 接口优先稳定

Agent 修改代码时，不得随意改变 `protocol/` 中的数据字段。确实需要修改时，必须同步更新：

- schema 文件；
- 模块 README；
- 测试数据；
- PROJECT_CONTEXT.md。

### 7.4 不把 LLM 作为唯一安全决策源

报警、排风、禁止进入等关键安全动作必须由本地规则兜底。云端 LLM 只用于：

- 风险解释；
- 处置建议；
- 报告生成；
- 多模型仲裁；
- 辅助决策。

### 7.5 每次开发必须可测试

Agent 每完成一个功能，必须同时提供：

- 如何编译；
- 如何运行；
- 如何单测；
- 预期输出；
- 常见错误排查。

---

## 8. 模块开发顺序

推荐按以下顺序开发：

```text
M1 传感器采集模块
M2 执行控制模块
M3 本地安全规则模块
M4 板间通信模块
M5 HMI 显示模块
M8 SafeCloud 云端模块
M7 语音交互模块
M6 视觉识别模块
M9 系统编排与日志模块
```

理由：

> 先保证系统能测、能判、能报警、能排风；再接入 HMI、云端、语音和视觉增强能力。

---

## 9. 统一数据协议初稿

### 9.1 传感器数据包

```json
{
  "device_id": "2k301-001",
  "timestamp": "2026-01-01T12:00:00",
  "temperature": 28.6,
  "humidity": 64.0,
  "tvoc": 620,
  "eco2": 850,
  "mq3_value": 732,
  "flame_detected": true
}
```

### 9.2 风险状态包

```json
{
  "risk_level": "L3",
  "risk_name": "危急",
  "risk_reasons": [
    "挥发性气体异常",
    "火焰信号触发"
  ],
  "rule_hits": [
    "MQ3_HIGH",
    "FLAME_DETECTED",
    "VOC_AND_FLAME_COMBINED"
  ],
  "local_actions": [
    "RED_LED_FAST_BLINK",
    "BUZZER_CONTINUOUS",
    "FAN_MAX_SPEED"
  ]
}
```

### 9.3 云端安全事件包

```json
{
  "event_id": "evt-0001",
  "device_id": "2k1000la-001",
  "scene": "密闭空间演示舱",
  "timestamp": "2026-01-01T12:00:00",
  "sensor_data": {
    "temperature": 28.6,
    "humidity": 64.0,
    "tvoc": 620,
    "eco2": 850,
    "mq3_value": 732,
    "flame_detected": true
  },
  "vision_result": {
    "person_detected": true,
    "helmet_detected": false,
    "fire_detected": false,
    "ppe_status": "不合规"
  },
  "local_rule_result": {
    "risk_level": "L3",
    "rule_hits": [
      "MQ3_HIGH",
      "FLAME_DETECTED"
    ],
    "local_actions": [
      "声光报警",
      "最高速排风"
    ]
  }
}
```

### 9.4 云端仲裁结果包

```json
{
  "final_risk_level": "L3",
  "final_risk_name": "危急",
  "agreement": "3/4 模型判断为 L3，1/4 模型判断为 L2",
  "final_reasons": [
    "MQ-3 数值异常，提示挥发性气体风险",
    "FC-01 检测到火焰信号",
    "挥发性气体异常与火源同时存在，风险升级"
  ],
  "recommended_actions": [
    "禁止进入",
    "保持最高速排风",
    "清除火源",
    "等待传感器恢复正常后复检"
  ],
  "human_review_required": true,
  "confidence": 0.91,
  "report_summary": "当前环境存在挥发性气体与火源叠加风险，系统已触发危急级联动。"
}
```

---

## 10. 标准测试场景

系统至少需要支持以下测试场景：

| 场景 | 输入 | 期望输出 |
|---|---|---|
| S1 正常环境 | 所有传感器正常 | L0，绿灯，蜂鸣器静音，风扇停止 |
| S2 温湿度异常 | 温度或湿度超出设定范围 | L1，黄灯，提示观察 |
| S3 挥发物异常 | SGP30 或 MQ-3 升高 | L2，红灯慢闪，间歇报警，高速排风 |
| S4 火焰触发 | FC-01 触发 | L2 / L3，报警增强 |
| S5 挥发物 + 火焰 | MQ-3 异常且火焰触发 | L3，红灯快闪，连续报警，最高速排风 |
| S6 PPE 不合规 | 视觉检测未戴安全帽 | L1 / L2，禁止进入或要求整改 |
| S7 云端正常 | SafeCloud 在线 | 返回多 LLM 仲裁建议 |
| S8 云端超时 | 部分模型不可用 | 降级仲裁，本地安全不受影响 |
| S9 断网 | SafeCloud 不可用 | 本地规则继续报警和排风 |
| S10 语音查询 | 用户问“当前环境正常吗” | 播报当前风险等级和原因 |

---

## 11. 推荐提交规范

Git commit 建议格式：

```text
<type>(<module>): <summary>
```

示例：

```text
feat(sensor): add SHT temperature and humidity reader
feat(actuator): implement L0-L3 LED and buzzer policy
fix(protocol): align risk_level field with schema
 docs(agent): update development workflow
 test(cloud): add mock event for L3 hazard case
```

常用 type：

```text
feat     新功能
fix      修复问题
docs     文档
style    格式调整
refactor 重构
test     测试
chore    杂项
```

---

## 12. 给 Codex / Claude Code 的常用提示词

### 12.1 新模块开发

```text
请阅读 AGENTS.md、PROJECT_CONTEXT.md 和 protocol/ 下的数据协议。
现在开发 <模块名称>。
要求：
1. 不修改既有协议字段；
2. 当前模块必须能用模拟数据单独测试；
3. 提供 README 中的编译、运行、测试方法；
4. 不依赖尚未完成的模块；
5. 输出清晰日志。
```

### 12.2 修复编译错误

```text
请根据以下编译日志修复问题。
限制：
1. 不改变模块接口；
2. 不删除测试；
3. 修复后说明原因；
4. 给出重新编译命令。

编译日志：
<粘贴日志>
```

### 12.3 增加测试场景

```text
请为 <模块名称> 增加测试场景。
测试场景为：<描述场景>。
要求：
1. 使用 mock 数据；
2. 断言输出结果；
3. 更新 README 的测试说明；
4. 不依赖真实硬件。
```

### 12.4 自动化脚本开发

```text
请为本项目编写 <脚本名称>。
脚本目标：<目标>。
运行环境：Windows 通过 SSH 调用 Ubuntu VM。
要求：
1. 输出每一步日志；
2. 出错时返回非 0 退出码；
3. 支持配置远端主机名；
4. 不写死绝对路径；
5. 给出使用示例。
```

---

## 13. 初始建仓步骤

### 13.1 创建仓库目录

```bash
mkdir SafetyGuardian-Loongson
cd SafetyGuardian-Loongson
```

### 13.2 初始化 Git

```bash
git init
```

### 13.3 创建目录结构

```bash
mkdir -p docs/{architecture,hardware,software,test_plan,competition}
mkdir -p protocol
mkdir -p firmware_2k301/{src,include,tests}
mkdir -p app_2k1000la/{src,include,tests}
mkdir -p qt_hmi/{src,ui,resources,tests}
mkdir -p vision/{src,models,test_images}
mkdir -p voice/{src,wakeword,asr,tts}
mkdir -p safecloud/{app,api,llm_clients,judge,reports,tests}
mkdir -p scripts/{env,build,deploy,run,logs}
mkdir -p tests/{mock_data,integration,scenarios}
mkdir -p tools/{packet_sender,mock_sensor,mock_cloud,log_viewer}
```

### 13.4 创建基础文件

```bash
touch AGENTS.md PROJECT_CONTEXT.md README.md CHANGELOG.md TODO.md
```

### 13.5 首次提交

```bash
git add .
git commit -m "chore(repo): initialize safety guardian project structure"
```

---

## 14. AGENTS.md 初稿建议

可以在仓库根目录创建 `AGENTS.md`，内容如下：

```markdown
# AGENTS.md

本项目为“基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪”。

## 最高原则

1. 端侧安全优先，云端智能增强。
2. 报警、排风等关键动作必须有本地规则兜底。
3. 当前开发哪个模块，其它模块使用 mock 数据替代。
4. 不允许随意修改 protocol/ 下的协议字段。
5. 每次修改必须保证可编译、可测试、可回滚。
6. 不直接在开发板上编辑源码。
7. Windows 负责开发，Linux VM 负责编译，龙芯板负责运行验证。

## 当前硬件

- 龙芯 2K1000LA：主控、HMI、视觉、语音、云端通信。
- 龙芯 2K0301：传感器采集与执行控制。
- 传感器：FC-01、SHT、SGP30、MQ-3。
- 执行器：三色灯、蜂鸣器、TB6612 + 直流电机。
- 交互：USB 声卡 / 播放器、语音唤醒与播报。

## 开发顺序

M1 传感器采集 → M2 执行控制 → M3 本地规则 → M4 板间通信 → M5 HMI → M8 云端 → M7 语音 → M6 视觉 → M9 系统集成。
```

---

## 15. PROJECT_CONTEXT.md 初稿建议

可以在仓库根目录创建 `PROJECT_CONTEXT.md`，内容如下：

```markdown
# PROJECT_CONTEXT.md

## 项目名称

基于龙芯双处理器与多 LLM 仲裁的密闭空间智能安全监护仪

## 应用场景

面向化工储罐、地下管廊等密闭空间作业场景，实现环境监测、视觉认知、风险分级、语音交互、云端多 LLM 仲裁、声光报警和强制排风。

## 系统定位

本项目属于嵌入式设计大赛方向二：基于 LLM 的智能检测工业仪器设计。

## 总体架构

2K0301 负责传感器采集与执行控制；2K1000LA 负责 HMI、视觉、语音、本地规则和云端通信；SafeCloud 负责多模型推理、Safety-Judge 仲裁和报告生成。

## 当前传感器

- SHT：温湿度
- SGP30：TVOC / eCO₂
- MQ-3：酒精 / 乙醇类挥发物
- FC-01：火焰检测

## 当前执行器

- 三色指示灯
- 蜂鸣器
- TB6612 电机驱动
- 直流电机模拟排风

## 风险等级

- L0：正常
- L1：注意
- L2：警戒
- L3：危急

## 核心安全原则

LLM 不直接作为唯一安全执行依据。关键报警和排风动作由本地规则直接触发，LLM 负责解释、建议、仲裁和报告生成。
```

---

## 16. 当前最先执行的任务

建议建仓后按以下顺序做：

```text
1. 创建仓库目录结构
2. 写入 AGENTS.md 与 PROJECT_CONTEXT.md
3. 写入 protocol/ 下的 JSON schema 初稿
4. 写 M1 传感器采集模块 mock 版本
5. 写 M2 执行控制模块 mock 版本
6. 写一键 build/deploy/run 脚本雏形
7. 再开始连接真实硬件
```

第一阶段目标：

> 即使没有任何硬件，也能用 mock 数据跑通“传感器数据 → 风险等级 → 执行动作状态”的软件流程。
