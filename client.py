import os
import json
import asyncio
from dotenv import load_dotenv
import httpx
import argparse
import logging
import inspect
from typing import Dict, Any, List, Optional, Callable, Union, Awaitable

# 设置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# LangChain导入
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import BaseTool, tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.callbacks.base import BaseCallbackHandler
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

# 加载环境变量
load_dotenv()

# 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("请在.env文件中设置DEEPSEEK_API_KEY")

# MCP服务器地址 - 默认使用8765端口
DEFAULT_MCP_PORT = 8765
MCP_SERVER_URL = f"http://localhost:{DEFAULT_MCP_PORT}/v1/mcp"

# 自定义回调处理器，记录工具调用过程
class MCPCallbackHandler(BaseCallbackHandler):
    """记录MCP工具调用过程的回调处理器"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        logger.debug(f"LLM开始思考，提示: {prompts[0][:100]}...")
        if self.verbose:
            print("\n" + "="*50)
            print("【LLM开始思考】")
    
    def on_llm_end(self, response, **kwargs):
        if self.verbose:
            print("\n" + "="*50)
            print("【LLM思考完成】")
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        logger.info(f"开始执行工具: {serialized.get('name', 'unknown')}, 输入: {input_str}")
        if self.verbose:
            print("\n" + "-"*50)
            print(f"【开始执行工具】: {serialized.get('name', 'unknown')}")
            print(f"输入参数: {input_str}")
    
    def on_tool_end(self, output, **kwargs):
        logger.info(f"工具执行完成，输出: {output[:100]}...")
        if self.verbose:
            print("\n" + "-"*50)
            print("【工具执行结果】")
            print(f"输出: {output}")
    
    def on_agent_action(self, action, **kwargs):
        logger.info(f"代理决定执行: {action.tool}, 输入: {action.tool_input}")
        if self.verbose:
            print("\n" + "="*50)
            print("【代理决策】")
            print(f"选择工具: {action.tool}")
            print(f"工具输入: {action.tool_input}")
            if hasattr(action, "log") and action.log:
                print(f"推理过程: {action.log}")

# 定义每个工具的参数模型
class WeatherParams(BaseModel):
    city: str = Field(description="城市名称，如北京、上海、广州等")

class ConverterParams(BaseModel):
    value: float = Field(description="要转换的数值")
    from_unit: str = Field(description="原始单位，如km、m、cm、kg、g、C、F等")
    to_unit: str = Field(description="目标单位，如km、m、cm、kg、g、C、F等")

class MCPClient:
    """MCP (Model Control Protocol) 客户端实现"""
    
    def __init__(self, server_url: str, llm_api_key: str):
        """
        初始化MCP客户端
        
        Args:
            server_url: MCP服务器URL
            llm_api_key: 大模型API密钥
        """
        self.server_url = server_url
        self.llm_api_key = llm_api_key
        
        # 初始化LangChain模型
        self.llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0,
            api_key=llm_api_key
        )
        
        # 本地函数注册表
        self.local_functions = {}
        
        # 创建MCP工具
        self.tools = [
            self._create_weather_tool(),
            self._create_converter_tool()
        ]
        
    def _create_weather_tool(self):
        """创建天气工具"""
        
        # 定义工具函数
        @tool(args_schema=WeatherParams)
        async def get_weather(city: str) -> str:
            """获取指定城市的天气信息，参数为城市名称，如北京、上海、广州等"""
            return await self._call_mcp_get_weather(city)
            
        return get_weather
        
    def _create_converter_tool(self):
        """创建单位转换工具"""
        
        @tool(args_schema=ConverterParams)
        async def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
            """单位转换工具，可以在不同单位之间转换值"""
            return await self._unit_converter(value, from_unit, to_unit)
            
        return unit_converter
    
    async def _call_mcp_get_weather(self, city: str) -> str:
        """调用MCP天气服务"""
        result = await self._call_mcp_function("get_weather", {"city": city})
        if "result" in result:
            weather = result["result"]
            return format_weather_response(weather)
        else:
            return f"获取天气信息失败: {result.get('error', '未知错误')}"
    
    async def _unit_converter(self, value: float, from_unit: str, to_unit: str) -> str:
        """本地实现的单位转换函数"""
        # 简单单位转换表
        conversions = {
            # 长度转换
            ("km", "m"): lambda x: x * 1000,
            ("m", "km"): lambda x: x / 1000,
            ("m", "cm"): lambda x: x * 100,
            ("cm", "m"): lambda x: x / 100,
            # 重量转换
            ("kg", "g"): lambda x: x * 1000,
            ("g", "kg"): lambda x: x / 1000,
            # 温度转换
            ("C", "F"): lambda x: x * 9/5 + 32,
            ("F", "C"): lambda x: (x - 32) * 5/9,
        }
        
        # 检查是否支持此转换
        key = (from_unit, to_unit)
        if key in conversions:
            result = conversions[key](value)
            return f"{value} {from_unit} = {result:.2f} {to_unit}"
        else:
            return f"不支持从 {from_unit} 到 {to_unit} 的转换"
    
    async def _call_mcp_function(self, function_name: str, parameters: Dict[str, Any]) -> Dict:
        """
        调用MCP服务器上的函数
        
        Args:
            function_name: 函数名称
            parameters: 函数参数
            
        Returns:
            函数调用结果
        """
        logger.info(f"MCP函数调用: {function_name}({parameters})")
        
        try:
            # 构建MCP请求
            mcp_request = {
                "function_name": function_name,
                "parameters": parameters
            }
            
            # MCP协议: 发送函数调用请求到服务器
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.server_url,
                    json=mcp_request,
                    timeout=10.0
                )
                
                # 处理MCP响应
                if response.status_code != 200:
                    logger.error(f"MCP服务器错误: {response.status_code}")
                    return {"error": f"MCP错误 ({response.status_code})"}
                
                result = response.json()
                logger.info(f"MCP响应成功: {function_name}")
                return result
                
        except Exception as e:
            logger.error(f"MCP函数调用出错: {str(e)}")
            return {"error": str(e)}
    
    async def handle_query(self, query: str, verbose: bool = False) -> str:
        """
        处理用户查询
        
        Args:
            query: 用户查询
            verbose: 是否显示详细日志
            
        Returns:
            处理结果
        """
        # 构建系统提示
        system_message = """
        你是一个功能强大的助手，使用MCP (Model Control Protocol) 协议与外部系统交互。
        
        MCP协议允许你调用以下函数:
        
        1. get_weather: 获取指定城市的天气信息
           - 参数: city (城市名称，如北京、上海、广州等)
        
        2. unit_converter: 在不同单位之间转换值
           - 参数: value (要转换的数值)，from_unit (原始单位)，to_unit (目标单位)
           - 支持的单位: km/m/cm(长度)、kg/g(重量)、C/F(温度)
        
        当用户请求需要实时数据或特定计算时，你应该:
        1. 分析用户需求，确定是否需要外部数据
        2. 选择合适的MCP函数
        3. 准备所需参数
        4. 调用函数获取结果
        5. 基于结果提供答案
        
        在决策过程中，请清晰解释你的推理:
        
        推理分析: [解释你如何理解用户需求以及为什么选择特定函数]
        MCP函数选择: [说明选择哪个函数以及为什么]
        参数准备: [说明每个参数如何从用户请求中提取或推断]
        """
        
        if verbose:
            print(f"\n用户查询: {query}")
            print("="*50)
            print("使用LangChain处理查询...")
        
        try:
            # 创建LangChain提示模板
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            
            # 创建代理
            agent = create_openai_tools_agent(self.llm, self.tools, prompt)
            
            # 创建回调处理器
            callbacks = [MCPCallbackHandler(verbose=verbose)]
            
            # 创建并配置代理执行器
            agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=verbose,
                callbacks=callbacks,
                handle_parsing_errors=True,
                return_intermediate_steps=True
            )
            
            # 执行代理
            response = await agent_executor.ainvoke({"input": query})
            
            # 显示中间步骤
            if verbose and "intermediate_steps" in response:
                print("\n" + "="*50)
                print("代理执行完成，中间步骤摘要:")
                print("="*50)
                
                for i, step in enumerate(response["intermediate_steps"]):
                    action, observation = step
                    print(f"\n步骤 {i+1} 简要:")
                    print(f"选择工具: {action.tool}")
                    print(f"工具参数: {action.tool_input}")
                    print(f"工具返回: {observation[:100]}..." if len(str(observation)) > 100 else f"工具返回: {observation}")
            
            return response["output"]
            
        except Exception as e:
            logger.error(f"处理查询出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"处理查询时发生错误: {str(e)}"

# 辅助函数：格式化天气信息
def format_weather_response(weather):
    """格式化天气信息"""
    return (f"{weather['city']}的天气情况：\n"
            f"温度：{weather['temperature']}°C，体感温度：{weather['feels_like']}°C\n"
            f"天气：{weather['description']}\n"
            f"湿度：{weather['humidity']}%\n"
            f"风速：{weather['wind_speed']}m/s")

async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="MCP 天气查询客户端")
    parser.add_argument("--port", type=int, default=DEFAULT_MCP_PORT, 
                        help=f"MCP服务器端口号，默认{DEFAULT_MCP_PORT}")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="显示详细日志")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="启用调试日志")
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    # 更新MCP服务器URL
    mcp_server_url = f"http://localhost:{args.port}/v1/mcp"
    
    print(f"=== MCP协议 + LangChain 天气查询示例 ===")
    print(f"连接到MCP服务器: {mcp_server_url}")
    print("输入'退出'结束程序")
    
    # 创建MCP客户端
    mcp_client = MCPClient(mcp_server_url, DEEPSEEK_API_KEY)
    
    while True:
        user_input = input("\n请输入您的天气查询: ")
        if user_input.lower() in ["退出", "exit", "quit"]:
            break
        
        # 使用MCP客户端处理查询
        result = await mcp_client.handle_query(user_input, args.verbose)
        print("\n" + result)

if __name__ == "__main__":
    asyncio.run(main()) 