# 标准库导入
import json
import logging
from decimal import Decimal
from datetime import datetime

# 导入OKX需要的模块
import okx.Trade as Trade

# 设置日志记录器
logger = logging.getLogger(__name__)

class DemoTradeManager:
    """
    模拟盘交易管理器
    用于处理OKX模拟盘的交易操作
    """
    
    def __init__(self, api_key, secret_key, passphrase):
        """
        初始化模拟交易管理器
        
        参数:
            api_key (str): OKX API密钥
            secret_key (str): OKX API密钥对应的秘钥
            passphrase (str): API密码短语
        """
        self.tradeAPI = Trade.TradeAPI(
            api_key,
            secret_key,
            passphrase,
            {"x-simulated-trading": "1"},  # 强制使用模拟交易
            "1"  # 强制使用模拟盘
        )
        
    async def place_order(self, inst_id: str, side: str, amount: Decimal) -> dict:
        """
        下单函数
        
        参数:
        - inst_id: 产品ID，例如："SOL-USDT-SWAP"
        - side: 订单方向，"buy" 或 "sell"
        - amount: 委托数量
        
        返回:
        - dict: 订单结果
        """
        try:
            # 验证参数
            if not inst_id or not side or not amount:
                return {
                    "success": False,
                    "message": "参数不完整",
                    "data": None
                }
            
            # 验证订单方向
            if side not in ["buy", "sell"]:
                return {
                    "success": False,
                    "message": "无效的订单方向",
                    "data": None
                }
            
            # 验证是否是合约交易
            if not inst_id.endswith('-SWAP'):
                return {
                    "success": False,
                    "message": "模拟盘仅支持合约交易",
                    "data": None
                }
            
            # 准备订单参数
            order_data = {
                "instId": inst_id,        # 产品ID
                "tdMode": "cash",         # 交易模式：现金
                "side": side,             # 订单方向
                "ordType": "market",      # 市价单
                "sz": str(amount)         # 委托数量
            }
            
            # 发送订单
            result = self.tradeAPI.place_order(**order_data)
            
            # 记录订单信息
            with open('demo_order_history.txt', 'a') as file:
                json.dump({
                    "timestamp": str(datetime.now()),
                    "order": order_data,
                    "result": result
                }, file, indent=4)
                file.write('\n')
            
            # 处理响应
            if result.get('code') == '0':
                return {
                    "success": True,
                    "message": "模拟盘下单成功",
                    "data": result.get('data', [])
                }
            else:
                return {
                    "success": False,
                    "message": f"模拟盘下单失败: {result.get('msg', '未知错误')}",
                    "data": None
                }
                
        except Exception as e:
            logger.error(f"模拟盘下单错误: {str(e)}")
            return {
                "success": False,
                "message": f"系统错误: {str(e)}",
                "data": None
            }