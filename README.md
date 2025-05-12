# MCP天气查询示例

这是一个使用MCP (Model Control Protocol) 协议的天气查询示例应用，使用DeepSeek大模型和OpenWeatherMap API实现。

## 功能

- 通过DeepSeek大模型理解用户的天气查询意图
- 使用OpenWeatherMap API获取实时天气数据
- 实现MCP协议的服务端和客户端

## 安装

1. 克隆仓库并进入项目目录
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置API密钥：
   - 在[OpenWeatherMap](https://openweathermap.org/)注册并获取API密钥
   - 在[DeepSeek](https://platform.deepseek.com)注册并获取API密钥
   - 更新`.env`文件中的API密钥：

```
OPENWEATHERMAP_API_KEY=your_openweathermap_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## 使用方法

1. 启动MCP服务器：

```bash
python server.py
```

2. 在另一个终端中启动客户端：

```bash
python client.py
```

3. 在客户端中输入您的天气查询，例如：
   - "北京今天的天气怎么样？"
   - "上海的气温是多少？"
   - "深圳会下雨吗？"

## MCP协议说明

本项目实现了简单的MCP协议：

- **服务端**：提供`/v1/mcp`端点，处理客户端发来的函数调用请求
- **客户端**：使用大模型理解用户意图，通过MCP协议调用服务端函数

### 支持的函数

- `get_weather`：获取指定城市的天气信息
  - 参数：`city` - 城市名称

## 技术栈

- FastAPI：构建MCP服务器
- DeepSeek：理解用户意图并生成响应
- OpenWeatherMap API：提供天气数据
- httpx：异步HTTP客户端
- asyncio：异步编程 