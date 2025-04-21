# 标准库导入
import asyncio
import json
import logging
import ssl
from decimal import Decimal
from datetime import datetime

#导入OKX需要的模块
import okx.Funding as Funding
import okx.Account as Account

# 第三方库导入
import aiohttp
import base58
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

#本代码使用OKX交易所进行交易！

# 设置日志记录器
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 设置 httpx 和其他库的日志级别为 WARNING
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# 配置常量
CONFIG = {
    'TOKEN': "7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA",  # Telegram Bot Token
    'ADMIN_CHAT_ID': 7792247162,
    'WALLET_FILE': "wallets.json",  # 添加钱包文件配置
    'OKX_API': {
        'BASE_URL': 'https://www.okx.com',
        'TICKER_PATH': '/api/v5/market/ticker',
        'API_KEY': "096b91c1-2b92-4880-bda4-90b3ecb0c44e",
        'SECRET_KEY': "9C42297797BDF0063A02FFE3D7417B6A",
        'PASSPHRASE': "1qaz@WSX12",
        'FLAG': "0"  # 实盘: 0, 模拟盘: 1
    }
}

# UI 常量定义
TRADE_MENU = """
💼 <b>Solana 交易菜单</b>

请选择要执行的操作：
"""

MAIN_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔗 连接钱包", callback_data="connect_wallet")],
    [InlineKeyboardButton("👛 当前钱包", callback_data="current_wallet")],
    [InlineKeyboardButton("💰 购买代币", callback_data="buy")],
    [InlineKeyboardButton("💱 出售代币", callback_data="sell")],
    [InlineKeyboardButton("⚙️ 设置", callback_data="settings")]
])

# 工具函数
def is_valid_solana_address(address: str) -> bool:
    """验证 Solana 钱包地址"""
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except:
        return False

async def get_wallet_balance_solanabeach(address: str) -> tuple:
    """从 Solanabeach 获取钱包余额"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            url = f"{CONFIG['SOLANA_RPC_URLS']['solanabeach']}/account/{address}"
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {CONFIG['API_KEYS']['solanabeach']}"
            }
            
            # 创建自定义 SSL 上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=ssl_context) as response:
                    if response.status == 500:
                        logger.error(f"Solanabeach API 服务器错误 (尝试 {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            continue
                        return None
                    
                    if response.status != 200:
                        logger.error(f"Solanabeach API 错误: {response.status}")
                        return None
                    
                    data = await response.json()
                    if data.get("value", {}).get("base", {}).get("balance") is not None:
                        balance_sol = float(data["value"]["base"]["balance"]) / 1e9
                        return balance_sol
                    logger.warning(f"Solanabeach 响应格式错误: {data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Solanabeach 查询错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return None
    
    return None

async def get_wallet_balance_rpc(address: str, network: str = 'devnet') -> float:
    """从 RPC 节点获取钱包余额"""
    try:
        rpc_url = CONFIG['SOLANA_RPC_URLS'][network]
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        
        # 创建自定义 SSL 上下文
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # 设置更短的超时时间
        timeout = aiohttp.ClientTimeout(total=3, connect=2)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(rpc_url, json=payload, headers=headers, ssl=ssl_context) as response:
                if response.status != 200:
                    print(f"RPC 节点响应错误: {response.status}")
                    return 0.0
                
                data = await response.json()
                if "result" in data:
                    balance_sol = float(data["result"]) / 1e9
                    return balance_sol
                return 0.0
    except asyncio.TimeoutError:
        print(f"RPC 节点 {network} 连接超时")
        return 0.0
    except Exception as e:
        print(f"查询余额错误: {e}")
        return 0.0
async def get_wallet_balance(address: str) -> tuple:
    """获取钱包余额"""
    try:
        # 初始化OKX API
        accountAPI = Account.AccountAPI(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取账户余额
        result = accountAPI.get_account_balance()
        
        # 保存账户余额到文件
        with open('currencies.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        trading_balance = 0.0  # 交易账户余额
        funding_balance = 0.0  # 资金账户余额
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'  # 添加币种信息
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                sol_detail = next((detail for detail in details if detail.get('ccy') == 'SOL'), None)
                if sol_detail:
                    trading_balance = float(sol_detail.get('availBal', 0))  # 交易账户可用余额
                    funding_balance = float(sol_detail.get('cashBal', 0))   # 资金账户余额
                    usd_value = float(sol_detail.get('eqUsd', 0))
                    currency = sol_detail.get('ccy', 'UNKNOWN')  # 获取币种信息
                    break
        
        return (round(trading_balance, 4), round(funding_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')

async def get_sol_price_okx() -> float:
    """从 OKX 获取 SOL 当前价格"""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{CONFIG['OKX_API']['BASE_URL']}/api/v5/market/ticker"
            params = {'instId': 'SOL-USDT-SWAP'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"OKX API 错误: {response.status}")
                    return 0.0
                
                data = await response.json()
                if data.get('code') == '0' and data.get('data'):
                    ticker_data = data['data'][0]
                    mark_price = float(ticker_data.get('markPx', 0))
                    last_price = float(ticker_data.get('last', 0))
                    return mark_price or last_price
                
                logger.error(f"OKX API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        logger.error(f"获取 OKX 价格错误: {e}")
        return 0.0

async def get_sol_price() -> float:
    """获取 SOL 当前价格"""
    try:
        price = await get_sol_price_okx()
        return price if price > 0 else 0.0
    except Exception as e:
        print(f"获取价格错误: {e}")
        return 0.0

# 钱包存储相关函数
def load_wallets():
    """从文件加载钱包数据"""
    try:
        with open(CONFIG['WALLET_FILE'], 'r') as f:
            wallets_data = json.load(f)
            return {int(user_id): address for user_id, address in wallets_data.items()}
    except FileNotFoundError:
        return {}

def save_wallets(wallets):
    """保存钱包数据到文件"""
    wallets_data = {str(user_id): address for user_id, address in wallets.items()}
    with open(CONFIG['WALLET_FILE'], 'w') as f:
        json.dump(wallets_data, f)

# 初始化用户钱包存储
user_wallets = load_wallets()

# RPC 节点相关函数
async def test_rpc_node(network='testnet'):
    """测试指定网络的 RPC 节点"""
    try:
        rpc_url = CONFIG['SOLANA_RPC_URLS'][network]
        print(f"正在测试 {network} RPC 节点: {rpc_url}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getVersion",
            "params": []
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(rpc_url, json=payload, headers=headers) as response:
                end_time = asyncio.get_event_loop().time()
                response_time = round((end_time - start_time) * 1000)
                
                if response.status != 200:
                    return False, response_time, f"HTTP 错误: {response.status}"
                
                data = await response.json()
                
                if "error" in data:
                    return False, response_time, f"RPC 错误: {data['error']}"
                
                if "result" in data:
                    version = data["result"].get("solana-core", "未知")
                    feature_set = data["result"].get("feature-set", "未知")
                    print(f"节点版本: {version}, 特性集: {feature_set}")
                    return True, response_time, f"版本: {version}"
                
                return False, response_time, "无效的响应格式"
                
        return False, 0, "请求失败"
    except asyncio.TimeoutError:
        return False, 10000, "请求超时"
    except Exception as e:
        return False, 0, f"错误: {str(e)}"

# Telegram 命令处理函数
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的 /start 命令")
    try:
        await update.message.reply_text(
            "👋 欢迎使用 Solana 交易助手！\n\n"
            "我可以帮助您：\n"
            "• 连接 Solana 钱包\n"
            "• 购买和出售代币\n"
            "• 查询账户余额\n"
            "• 管理交易设置\n\n"
            "请使用下方菜单进行操作："
        )
        print("已发送欢迎消息")
        
        await update.message.reply_text(
            text=TRADE_MENU,
            parse_mode='HTML',
            reply_markup=MAIN_MENU_MARKUP
        )
        print("已发送主菜单")
    except Exception as e:
        print(f"发送菜单时出错: {e}")
        await update.message.reply_text("抱歉，显示菜单时出现错误。")

async def test_nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /test_nodes 命令"""
    message = await update.message.reply_text("正在测试 RPC 节点，请稍候...")

    results = []
    for network in CONFIG['SOLANA_RPC_URLS']:
        success, response_time, info = await test_rpc_node(network)
        status = "✅ 正常" if success else "❌ 异常"
        results.append(f"{network}: {status} ({response_time}ms) - {info}")
    
    result_text = "🔍 RPC 节点测试结果:\n\n" + "\n".join(results)
    await message.edit_text(result_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息"""
    user = update.effective_user
    text = update.message.text
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的消息: {text}")
    
    if is_valid_solana_address(text):
        msg = await update.message.reply_text("正在验证钱包地址...")
        
        try:
            balance, usd_value = await get_wallet_balance(text)
            user_wallets[user.id] = text
            save_wallets(user_wallets)
            
            await msg.edit_text(
                f"🎉 钱包连接成功！\n\n"
                f"📍 地址: {text}\n"
                f"💰 余额: {balance}\n"
                f"💵 估值: {usd_value} USD\n\n"
                "现在你可以开始交易了！",
                reply_markup=MAIN_MENU_MARKUP
            )
        except Exception as e:
            print(f"钱包连接错误: {e}")
            await msg.edit_text(
                "❌ 连接失败！\n"
                "请检查钱包地址是否正确，或稍后重试。"
            )
        return

    try:
        amount = Decimal(text)
        await update.message.reply_text(f"收到金额：{amount}\n处理中...")
        print(f"处理金额: {amount}")
    except:
        await update.message.reply_text("请输入有效的数字金额或 Solana 钱包地址")
        print("无效的输入")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        if query.data == "current_wallet":
            if user_id in user_wallets:
                wallet = user_wallets[user_id]
                trading_balance, funding_balance, usd_value, balance_source, currency = await get_wallet_balance(wallet)
                
                new_text = (
                    f"📱 当前连接的钱包信息：\n\n"
                    f"📍 地址: {wallet}\n"
                    f"💰 交易账户余额: {trading_balance} {currency} ({balance_source})\n"
                    f"💵 交易账户估值: ${usd_value} (OKX)\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💳 资金账户余额: {funding_balance} {currency} ({balance_source})\n"
                    f"💵 资金账户估值: 资金账户暂不提供估值，可用交易账户参考！\n"
                    f"🕒 更新时间: {datetime.now().strftime('%H:%M:%S')}"
                )
                
                try:
                    await query.message.edit_text(
                        new_text,
                        reply_markup=MAIN_MENU_MARKUP
                    )
                except Exception as e:
                    if "Message is not modified" not in str(e):
                        raise e
            else:
                await query.message.edit_text(
                    "❌ 还未连接钱包！\n"
                    "请点击「🔗 连接钱包」按钮进行连接。",
                    reply_markup=MAIN_MENU_MARKUP
                )
        elif query.data == "connect_wallet":
            await query.message.reply_text(
                "🔗 请选择要连接的钱包：\n\n"
                "1. 发送你的 Solana 钱包地址\n"
                "2. 或者使用以下命令：\n"
                "/connect <钱包地址>"
            )
        elif query.data == "buy":
            await query.message.reply_text("请输入要购买的代币数量：")
        elif query.data == "sell":
            await query.message.reply_text("请输入要出售的代币数量：")
        elif query.data == "settings":
            await query.message.reply_text("设置功能开发中...")
            
    except Exception as e:
        print(f"处理按钮点击错误: {e}")
        await query.message.reply_text("处理请求时出错，请重试。")

async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """调试所有收到的消息"""
    try:
        print("\n=== 收到新消息 ===")
        if hasattr(update, 'message') and update.message:
            print(f"消息类型: {update.message.__class__.__name__}")
            print(f"消息内容: {update.message.text}")
            print(f"发送者ID: {update.effective_user.id}")
            print(f"发送者名称: {update.effective_user.first_name}")
        print("==================")
    except Exception as e:
        print(f"调试处理器错误: {e}")
        pass

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    print(f'发生错误: {context.error}')
    logger.error(f'Update {update} caused error {context.error}')

# 主程序
async def main():
    """启动机器人"""
    print('\n=== Solana 交易助手 ===')
    print('正在初始化...')
    
    global user_wallets
    user_wallets = load_wallets()
    print(f'已加载 {len(user_wallets)} 个钱包')
    
    try:
        app = (
            Application.builder()
            .token(CONFIG['TOKEN'])
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )

        handlers = [
            CommandHandler("start", start),
            CommandHandler("test_nodes", test_nodes),
            CallbackQueryHandler(handle_button),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.ALL, debug_handler)
        ]
        
        for handler in handlers:
            app.add_handler(handler)
        
        app.add_error_handler(error)
        
        print('所有处理程序注册完成')

        async with app:
            await app.initialize()
            await app.start()
            
            await app.bot.send_message(
                chat_id=CONFIG['ADMIN_CHAT_ID'],
                text="🚀 Solana 交易助手已启动！\n\n发送 /start 开始交易"
            )
            
            print('\n机器人已成功启动！')
            print('在 Telegram 中发送 /start 开始使用')
            print('按 Ctrl+C 可停止机器人\n')
            
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
            
    except Exception as e:
        logger.error(f'启动错误: {e}')
        print('请检查配置是否正确')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n收到退出信号，机器人已停止")
async def get_sol_price_binance() -> float:
    """从 Binance 获取 SOL 当前价格"""
    try:
        timeout = aiohttp.ClientTimeout(total=3, connect=2)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = "https://api.binance.com/api/v3/ticker/price"
            params = {'symbol': 'SOLUSDT'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    print(f"Binance API 错误: {response.status}")
                    return 0.0
                
                data = await response.json()
                if 'price' in data:
                    price = float(data['price'])
                    print(f"Binance SOL 价格: ${price}")
                    return price
                
                print(f"Binance API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        print(f"获取 Binance 价格错误: {e}")
        return 0.0

async def get_wallet_balance(address: str) -> tuple:
    """获取钱包余额"""
    try:
        # 并行执行余额和价格查询
        balance_task = get_wallet_balance_solanabeach(address)
        price_task = get_sol_price_binance()
        
        balance, sol_price = await asyncio.gather(balance_task, price_task)
        
        # 如果 Solana Beach 查询失败，尝试备用节点
        if balance is None:
            print("Solana Beach 查询失败，使用备用节点")
            balance = await get_wallet_balance_rpc(address, 'devnet')
            balance_source = 'Solana Devnet'
        else:
            balance_source = 'Solana Beach'
        
        if balance > 0 and sol_price > 0:
            usd_value = balance * sol_price
            return (round(balance, 4), round(usd_value, 2), balance_source)
        
        return (round(balance, 4) if balance else 0.0, 0.0, balance_source)
            
    except Exception as e:
        print(f"获取钱包信息错误: {e}")
        return (0.0, 0.0, 'Unknown')
