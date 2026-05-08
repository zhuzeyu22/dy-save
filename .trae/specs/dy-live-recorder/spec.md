# 抖音直播录音方案规格

## Why
需要自动化记录抖音主播"智慧的大聪明"的直播内容，包括：24小时监控直播状态、录制直播音频、处理多人连麦场景、实现语音转文本并按音色区分说话者，最终归档到Obsidian笔记系统。

## What Changes

- **新增**: 抖音直播监控模块 - 定时检测主播是否在直播
- **新增**: 音频录制模块 - 直播时持续录制原始音频
- **新增**: 语音识别模块 - 实时语音转文本
- **新增**: 声纹识别模块 - 根据音色区分不同说话者
- **新增**: Obsidian同步模块 - 将转录内容记录到Obsidian
- **新增**: 配置文件管理 - 支持多账号配置

## Impact
- 新增依赖：`playwright`/`mitmproxy`（抖音抓流）、`faster-whisper`（语音识别）、`pyannote-audio`（声纹识别）、`obsidian-api`
- 核心文件：
  - `dy_monitor.py` - 主程序入口
  - `config.yaml` - 配置文件
  - `obsidian/` - Obsidian笔记模板

## ADDED Requirements

### Requirement: 抖音直播监控
系统 SHALL 每5分钟检测一次主播"智慧的大聪明"是否正在直播

#### Scenario: 主播未开播
- **WHEN** 主播当前未在直播
- **THEN** 系统进入待机状态，打印"待机中"，5分钟后再次检测

#### Scenario: 主播开播
- **WHEN** 主播开始直播
- **THEN** 系统立即开始录制音频，并记录直播开始时间

### Requirement: 音频录制
系统 SHALL 在直播期间持续录制音频流，保存为WAV格式

#### Scenario: 录制过程中
- **WHEN** 正在直播
- **THEN** 以16kHz采样率、16位深、单声道录制音频
- **AND** 每30分钟保存一个分片文件
- **AND** 文件命名格式：`{日期}_{开始时间}_part{N}.wav`

#### Scenario: 直播结束
- **WHEN** 检测到直播结束（超过10分钟无直播流）
- **THEN** 保存当前分片
- **AND** 合并所有分片为一个完整文件
- **AND** 触发转录流程

### Requirement: 语音转文本
系统 SHALL 将录制的音频转换为带时间戳的文本

#### Scenario: 转录处理
- **WHEN** 接收到完整录音文件
- **THEN** 使用Whisper模型进行语音识别
- **AND** 输出包含：开始时间、结束时间、文本内容

### Requirement: 声纹识别区分说话者
系统 SHALL 根据音色将不同说话者的内容分开记录

#### Scenario: 多人对话场景
- **WHEN** 音频中包含多个说话者
- **THEN** 使用声纹识别技术区分说话者
- **AND** 为每个说话者分配唯一标识符（如：speaker_001, speaker_002）
- **AND** 在转录结果中标注每个片段的说话者

### Requirement: Obsidian归档
系统 SHALL 将转录内容记录到Obsidian笔记库

#### Scenario: 归档处理
- **WHEN** 转录完成且包含说话者标注
- **THEN** 在Obsidian指定Vault中创建每日笔记
- **AND** 笔记位置：`{vault}/Daily/{年}/{月}/{日}.md`
- **AND** 笔记格式包含：
  - 直播时间段
  - 各说话者的发言记录
  - 原始音频文件链接

### Requirement: 配置管理
系统 SHALL 通过配置文件管理所有参数

#### Scenario: 配置文件加载
- **WHEN** 系统启动
- **THEN** 读取`config.yaml`中的配置
- **AND** 支持的配置项：
  - `douyin.cookie` - 抖音登录Cookie
  - `douyin.room_id` - 主播房间号或主页链接
  - `record.quality` - 录音质量设置
  - `obsidian.vault_path` - Obsidian仓库路径
  - `obsidian.enabled` - 是否启用Obsidian同步
