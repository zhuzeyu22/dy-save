# Tasks

## 阶段一：环境准备
- [x] Task 1.1: 创建项目目录结构和配置文件 `config.yaml`
  - [x] 定义配置项结构（抖音账号、Obsidian路径、录音参数）
  - [x] 创建目录树：`obsidian_templates/`, `recordings/`, `output/`

## 阶段二：抖音直播监控模块
- [x] Task 2.1: 实现抖音API客户端
  - [x] 解析主播主页获取房间号
  - [x] 获取直播状态接口
  - [x] 获取直播推流地址（FLV流）
- [x] Task 2.2: 实现直播监控主循环
  - [x] 定时检测函数（默认5分钟间隔）
  - [x] 状态切换逻辑（待机→录制→待机）

## 阶段三：音频录制模块
- [x] Task 3.1: 实现RTMP/FLV流录制
  - [x] 使用ffmpeg下载直播流
  - [x] 配置音频参数（16kHz, 16bit, mono）
  - [x] 实现分片保存逻辑
- [x] Task 3.2: 实现录制状态管理
  - [x] 录制开始/结束检测
  - [x] 分片文件合并
  - [x] 异常处理和断线重连

## 阶段四：语音识别模块
- [x] Task 4.1: 集成Whisper模型
  - [x] 安装faster-whisper依赖
  - [x] 实现音频转文本函数
  - [x] 支持时间戳输出
- [x] Task 4.2: 批量转录处理
  - [x] 处理完整录音文件
  - [x] 分片转录后合并

## 阶段五：声纹识别模块
- [x] Task 5.1: 集成声纹识别模型
  - [x] 安装pyannote-audio依赖
  - [x] 实现说话者分割与识别（Diarization）
  - [x] 生成说话者索引
- [x] Task 5.2: 说话者标注整合
  - [x] 将声纹结果与Whisper转录合并
  - [x] 生成带说话者标签的输出

## 阶段六：Obsidian同步模块
- [x] Task 6.1: 实现Obsidian API客户端
  - [x] 连接本地Obsidian Vault
  - [x] 创建/更新日记文件
- [x] Task 6.2: 生成Obsidian笔记
  - [x] 应用笔记模板
  - [x] 格式化发言记录（按说话者分组）
  - [x] 添加元数据和链接

## 阶段七：主程序集成与测试
- [x] Task 7.1: 编写主程序入口 `dy_monitor.py`
  - [x] 整合所有模块
  - [x] 实现信号处理（优雅退出）
  - [x] 添加日志系统
- [x] Task 7.2: 创建启动脚本和文档
  - [x] `start.sh` - 一键启动
  - [x] `requirements.txt` - 依赖清单
  - [x] README使用说明

## Task Dependencies
- Task 2.1 完成后才能开始 Task 2.2 ✓
- Task 3.1 完成后才能开始 Task 3.2 ✓
- Task 4.1 完成后才能开始 Task 4.2 ✓
- Task 5.1 完成后才能开始 Task 5.2 ✓
- Task 4.2 和 Task 5.2 都完成后才能开始 Task 6.2 ✓
- Task 6.2 完成后才能开始 Task 7.1 ✓
- Task 7.1 完成后才能开始 Task 7.2 ✓
