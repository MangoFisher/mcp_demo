import os
import json
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
import argparse

# 加载环境变量
load_dotenv()

app = FastAPI(title="天气查询MCP服务器")

# 获取OpenWeatherMap API密钥
OPENWEATHER_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
if not OPENWEATHER_API_KEY:
    raise ValueError("请在.env文件中设置OPENWEATHERMAP_API_KEY")

# 中国主要城市ID映射
CHINA_CITY_IDS = {
    "北京": 1816670,
    "上海": 1796236,
    "广州": 1809858,
    "深圳": 1795565,
    "成都": 1815286,
    "重庆": 1814906,
    "杭州": 1808926,
    "武汉": 1791247,
    "西安": 1790630,
    "南京": 1799962,
    "天津": 1792947,
    "苏州": 1795940,
    "郑州": 1784658,
    "长沙": 1815577,
    "青岛": 1797929,
    "沈阳": 2034937,
    "大连": 1814087,
    "厦门": 1790923,
    "济南": 1805753
}

# MCP协议处理
class MCPRequest(BaseModel):
    function_name: str
    parameters: dict

@app.post("/v1/mcp")
async def handle_mcp_request(request: Request):
    body = await request.json()
    
    if "function_name" not in body or "parameters" not in body:
        raise HTTPException(status_code=400, detail="请求格式错误，缺少function_name或parameters")
    
    function_name = body["function_name"]
    parameters = body["parameters"]
    
    # 处理不同的函数
    if function_name == "get_weather":
        return await get_weather(parameters)
    else:
        raise HTTPException(status_code=404, detail=f"未找到函数: {function_name}")

async def get_weather(parameters):
    city = parameters.get("city")
    if not city:
        return {"error": "请提供城市名称"}
    
    # 打印接收到的城市名称
    print(f"接收到天气查询请求，城市: {city}")
    
    try:
        async with httpx.AsyncClient() as client:
            # 首先检查是否有城市ID
            city_id = CHINA_CITY_IDS.get(city)
            
            # 如果有城市ID，直接使用ID查询
            if city_id:
                print(f"使用城市ID查询: {city_id}")
                params = {
                    "id": city_id,
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                    "lang": "zh_cn"
                }
            else:
                # 针对中文城市名称，确保正确编码
                params = {
                    "q": city,
                    "appid": OPENWEATHER_API_KEY,
                    "units": "metric",
                    "lang": "zh_cn"
                }
            
            api_url = "http://api.openweathermap.org/data/2.5/weather"
            print(f"正在调用OpenWeatherMap API: {api_url}，参数: {params}")
            
            response = await client.get(api_url, params=params)
            
            # 记录API响应
            print(f"OpenWeatherMap API响应状态码: {response.status_code}")
            
            if response.status_code != 200:
                error_message = f"获取天气信息失败: {response.text}"
                print(error_message)
                
                # 如果使用城市名称查询失败，而且我们没有使用城市ID，尝试转换为英文
                if not city_id:
                    city_translations = {
                        "北京": "Beijing",
                        "上海": "Shanghai",
                        "广州": "Guangzhou",
                        "深圳": "Shenzhen",
                        "成都": "Chengdu",
                        "重庆": "Chongqing",
                        "杭州": "Hangzhou",
                        "武汉": "Wuhan",
                        "西安": "Xian",
                        "南京": "Nanjing",
                        "天津": "Tianjin",
                        "苏州": "Suzhou",
                        "郑州": "Zhengzhou",
                        "长沙": "Changsha",
                        "青岛": "Qingdao",
                        "沈阳": "Shenyang",
                        "大连": "Dalian",
                        "厦门": "Xiamen",
                        "济南": "Jinan"
                    }
                    
                    english_name = city_translations.get(city)
                    if english_name:
                        print(f"尝试使用英文名称查询: {english_name}")
                        response = await client.get(
                            "http://api.openweathermap.org/data/2.5/weather",
                            params={
                                "q": english_name,
                                "appid": OPENWEATHER_API_KEY,
                                "units": "metric",
                                "lang": "zh_cn"
                            }
                        )
                        
                        if response.status_code != 200:
                            print(f"使用英文名称查询依然失败: {response.text}")
                            return {
                                "error": error_message,
                                "status_code": response.status_code
                            }
                    else:
                        return {
                            "error": error_message,
                            "status_code": response.status_code
                        }
                else:
                    return {
                        "error": error_message,
                        "status_code": response.status_code
                    }
            
            # 解析天气数据
            weather_data = response.json()
            print(f"获取到天气数据: {json.dumps(weather_data)}")
            
            weather_info = {
                "city": weather_data["name"],
                "country": weather_data["sys"]["country"],
                "temperature": weather_data["main"]["temp"],
                "feels_like": weather_data["main"]["feels_like"],
                "description": weather_data["weather"][0]["description"],
                "humidity": weather_data["main"]["humidity"],
                "wind_speed": weather_data["wind"]["speed"],
                "weather_icon": weather_data["weather"][0]["icon"]
            }
            
            return {"result": weather_info}
            
    except Exception as e:
        error_message = f"获取天气信息时出错: {str(e)}"
        print(error_message)
        import traceback
        print(traceback.format_exc())
        return {"error": error_message}

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="MCP天气查询服务器")
    parser.add_argument("--port", type=int, default=8765, help="服务器端口号，默认8765")
    args = parser.parse_args()
    
    port = args.port
    print(f"MCP服务器正在启动，将监听端口: {port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True) 