# 标准库导入
import asyncio
import json
import logging
import traceback
from decimal import Decimal
from datetime import datetime

#导入OKX需要的模块
import okx.Funding as Funding
import okx.Account as Account
import okx.Trade as Trade  # 添加 Trade 模块导入

# 第三方库导入
import aiohttp
import base58
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from trade_bot_PostTrading import TradeManager
from trade_bot_DemoTrading import DemoTradeManager  # 添加模拟盘交易管理器导入

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
        'LIVE': {  # 实盘配置
            'API_KEY': "096b91c1-2b92-4880-bda4-90b3ecb0c44e",
            'SECRET_KEY': "9C42297797BDF0063A02FFE3D7417B6A",
            'PASSPHRASE': "1qaz@WSX12",
        },
        'DEMO': {  # 模拟盘配置
            'API_KEY': "84c23963-fa20-4bbb-b839-2430201e0b88",
            'SECRET_KEY': "B4F29DC1D45E9DC84290D58244D60005",
            'PASSPHRASE': "1qaz@WSX12",
        },
        'FLAG': "1"  # 1: 模拟盘, 0: 实盘
    },
    'TRADE': {
        'DEFAULT_INST_ID': 'SOL-USDT-SWAP',  # 默认交易对
        'MIN_AMOUNT': 0.0001,                    # 最小交易数量
        'MAX_AMOUNT': 100000                  # 最大交易数量
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
    [InlineKeyboardButton("💲 当前币价", callback_data="check_price")],
    [InlineKeyboardButton("⚙️ 设置", callback_data="settings")]
])

# 工具函数
def is_valid_solana_address(address: str) -> bool:
    """
    验证 Solana 钱包地址是否有效
    
    参数:
        address (str): 待验证的 Solana 钱包地址
        
    返回:
        bool: 如果地址有效返回 True，否则返回 False
    """
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except:
        return False

async def get_wallet_balance(address: str, crypto: str = 'SOL') -> tuple:
    """
    获取指定钱包地址的余额信息
    
    参数:
        address (str): Solana 钱包地址
        crypto (str): 虚拟币代码，默认为 'SOL'
        
    返回:
        tuple: 包含以下信息的元组:
            - trading_balance (float): 交易账户余额
            - cash_balance (float): 现金余额
            - usd_value (float): 美元估值
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化OKX API
        accountAPI = Account.AccountAPI(
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['API_KEY'],
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['SECRET_KEY'],
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['PASSPHRASE'],
            {"x-simulated-trading": "1"} if CONFIG['OKX_API']['FLAG'] == '1' else False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取交易账户余额
        result = accountAPI.get_account_balance()
        
        # 保存账户余额到文件
        with open('trading_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        trading_balance = 0.0  # 交易账户余额
        cash_balance = 0.0  # 币种余额
        usd_value = 0.0
        balance_source = 'OKX'
        currency = crypto  # 使用输入的币种
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                crypto_detail = next((detail for detail in details if detail.get('ccy') == crypto), None)
                if crypto_detail:
                    trading_balance = float(crypto_detail.get('availBal', 0))  # 交易账户可用余额
                    cash_balance = float(crypto_detail.get('cashBal', 0))   # 币种余额
                    usd_value = float(crypto_detail.get('eqUsd', 0))
                    break
        
        return (round(trading_balance, 4), round(cash_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', crypto)

async def get_funding_balance(address: str, crypto: str = 'SOL') -> tuple:
    """
    获取资金账户余额信息
    
    参数:
        address (str): Solana 钱包地址
        crypto (str): 虚拟币代码，默认为 'SOL'
        
    返回:
        tuple: 包含以下信息的元组:
            - balance (float): 总余额
            - available (float): 可用余额
            - frozen (float): 冻结余额
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化变量
        balance = 0.0
        available = 0.0
        frozen = 0.0
        balance_source = 'OKX'
        currency = crypto  # 使用输入的币种
        
        # 初始化OKX Funding API
        fundingAPI = Funding.FundingAPI(
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['API_KEY'],
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['SECRET_KEY'],
            CONFIG['OKX_API']['DEMO' if CONFIG['OKX_API']['FLAG'] == '1' else 'LIVE']['PASSPHRASE'],
            {"x-simulated-trading": "1"} if CONFIG['OKX_API']['FLAG'] == '1' else False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取资金账户余额
        result = fundingAPI.get_balances()
        
        # 保存资金账户余额到文件
        with open('funding_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        if isinstance(result, dict) and result.get('code') == '0':
            for balance_data in result.get('data', []):
                if balance_data.get('ccy') == crypto:  # 使用传入的币种代码
                    balance = float(balance_data.get('bal', 0))
                    available = float(balance_data.get('availBal', 0))
                    frozen = float(balance_data.get('frozenBal', 0))
                    break
        
        return (round(balance, 4), round(available, 4), round(frozen, 4), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX资金账户信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', crypto)

async def get_sol_price_okx() -> float:
    """
    从 OKX 交易所WebSocket公共频道获取 SOL 当前价格
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        # WebSocket连接URL
        ws_url = 'wss://wspap.okx.com:8443/ws/v5/public'
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            # 如果是模拟盘，添加模拟交易标记
            if CONFIG['OKX_API']['FLAG'] == '1':
                headers["x-simulated-trading"] = "1"
                
            async with session.ws_connect(ws_url, ssl=False, headers=headers) as ws:
                # 订阅Tickers频道
                subscribe_message = {
                    "op": "subscribe",
                    "args": [{
                        "channel": "tickers",
                        "instId": CONFIG['TRADE']['DEFAULT_INST_ID']
                    }]
                }
                
                await ws.send_json(subscribe_message)
                
                # 等待接收数据
                try:
                    async with asyncio.timeout(5):  # 设置5秒超时
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                
                                # 检查是否是行情数据
                                if data.get('event') == 'subscribe':
                                    continue
                                
                                if 'data' in data:
                                    ticker_data = data['data'][0]
                                    mark_price = float(ticker_data.get('markPx', 0))
                                    last_price = float(ticker_data.get('last', 0))
                                    
                                    price = mark_price or last_price
                                    if price > 0:
                                        logger.info(f"WebSocket成功获取SOL价格: ${price}")
                                        return price
                            
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"WebSocket错误: {msg.data}")
                                return 0.0
                                
                except asyncio.TimeoutError:
                    logger.error("WebSocket获取价格超时")
                    return 0.0
                    
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}, 错误类型: {type(e)}, 堆栈信息: {traceback.format_exc()}")
        return 0.0

async def get_sol_price() -> float:
    """
    获取 SOL 当前价格的封装函数
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        price = await get_sol_price_okx()
        return price if price > 0 else 0.0
    except Exception as e:
        print(f"获取价格错误: {e}")
        return 0.0

# 钱包存储相关函数
def load_wallets():
    """
    从保存的文件加载用户钱包数据
    
    返回:
        dict: 用户ID和钱包地址的映射字典，如果文件不存在返回空字典
    """
    try:
        with open(CONFIG['WALLET_FILE'], 'r') as f:
            wallets_data = json.load(f)
            return {int(user_id): address for user_id, address in wallets_data.items()}
    except FileNotFoundError:
        return {}

def save_wallets(wallets):
    """
    保存用户钱包数据到本地文件
    
    参数:
        wallets (dict): 用户ID和钱包地址的映射字典
    """
    wallets_data = {str(user_id): address for user_id, address in wallets.items()}
    with open(CONFIG['WALLET_FILE'], 'w') as f:
        json.dump(wallets_data, f)

# 初始化用户钱包存储
user_wallets = load_wallets()

# Telegram 命令处理函数
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理 Telegram /start 命令
    
    参数:
        update (Update): Telegram 更新对象
        context (ContextTypes.DEFAULT_TYPE): 回调上下文
    """
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
    """
    处理 /test_nodes 命令，测试 RPC 节点状态
    
    参数:
        update (Update): Telegram 更新对象
        context (ContextTypes.DEFAULT_TYPE): 回调上下文
    """
    message = await update.message.reply_text("正在测试 RPC 节点，请稍候...")

    results = []
    for network in CONFIG['SOLANA_RPC_URLS']:
        success, response_time, info = await test_rpc_node(network)
        status = "✅ 正常" if success else "❌ 异常"
        results.append(f"{network}: {status} ({response_time}ms) - {info}")
    
    result_text = "🔍 RPC 节点测试结果:\n\n" + "\n".join(results)
    await message.edit_text(result_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户消息的主函数
    """
    user = update.effective_user
    text = update.message.text
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的消息: {text}")
    
    # 处理等待币种输入状态
    if context.user_data.get('state') == 'waiting_for_crypto_balance':
        crypto = text.upper().strip() if text.strip() else 'SOL'
        wallet_address = user_wallets.get(user.id)
        
        msg = await update.message.reply_text(f"正在查询 {crypto} 余额...")
        
        try:
            trading_balance, cash_balance, usd_value, balance_source, currency = await get_wallet_balance(wallet_address, crypto)
            
            # 获取当前币价
            current_price = await get_sol_price_okx() if crypto == 'SOL' else 0.0
            price_info = f"\n💲 当前价格: ${current_price:.2f}" if current_price > 0 else ""
            
            trading_mode = "模拟盘" if CONFIG['OKX_API']['FLAG'] == '1' else "实盘"
            await msg.edit_text(
                f"📊 {crypto} 钱包信息 ({trading_mode})：\n\n"
                f"📍 地址: {wallet_address}\n"
                f"💰 可用余额: {trading_balance} {currency}\n"
                f"💵 总余额: {cash_balance} {currency}\n"
                f"💎 估值: ${usd_value} USD{price_info}\n"
                f"🏦 数据来源: {balance_source}",
                reply_markup=MAIN_MENU_MARKUP
            )
        except Exception as e:
            logger.error(f"查询钱包余额错误: {e}")
            await msg.edit_text(
                f"❌ 查询 {crypto} 余额失败！\n"
                "请检查币种代码是否正确，或稍后重试。",
                reply_markup=MAIN_MENU_MARKUP
            )
        
        # 重置用户状态
        context.user_data['state'] = None
        return
        
    if is_valid_solana_address(text):
        msg = await update.message.reply_text("正在验证钱包地址...")
        
        try:
            trading_balance, cash_balance, usd_value, balance_source, currency = await get_wallet_balance(text, 'SOL')
            user_wallets[user.id] = text
            save_wallets(user_wallets)
            
            await msg.edit_text(
                f"🎉 钱包连接成功！\n\n"
                f"📍 地址: {text}\n"
                f"💰 可用余额: {trading_balance} {currency}\n"
                f"💵 总余额: {cash_balance} {currency}\n"
                f"💎 估值: ${usd_value} USD\n\n"
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
        
        # 验证数量是否在允许范围内
        if amount < CONFIG['TRADE']['MIN_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太小，最小交易数量为 {CONFIG['TRADE']['MIN_AMOUNT']}")
            return
            
        if amount > CONFIG['TRADE']['MAX_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太大，最大交易数量为 {CONFIG['TRADE']['MAX_AMOUNT']}")
            return
        
        # 获取交易方向
        trade_action = context.user_data.get('trade_action', 'buy')  # 默认为买入
        
        # 检查账户余额
        trading_balance, cash_balance, usd_value, _, _ = await get_wallet_balance(user_wallets.get(user.id, ''))
        
        # 如果是买入，检查USDT余额；如果是卖出，检查SOL余额
        if trade_action == 'buy':
            current_price = await get_sol_price()
            if current_price <= 0:
                await update.message.reply_text("❌ 无法获取当前价格，请稍后重试")
                return
            required_balance = float(amount) * current_price
            if required_balance > cash_balance:
                await update.message.reply_text(
                    f"❌ 余额不足\n"
                    f"需要: {required_balance:.2f} USDT\n"
                    f"可用: {cash_balance:.2f} USDT"
                )
                return
        elif trade_action == 'sell':
            if float(amount) > trading_balance:
                await update.message.reply_text(
                    f"❌ SOL余额不足\n"
                    f"需要: {amount} SOL\n"
                    f"可用: {trading_balance} SOL"
                )
                return
        
        # 根据FLAG选择交易管理器
        trading_mode = "模拟盘" if CONFIG['OKX_API']['FLAG'] == '1' else "实盘"
        if CONFIG['OKX_API']['FLAG'] == '1':
            trade_manager = DemoTradeManager(
                CONFIG['OKX_API']['DEMO']['API_KEY'],
                CONFIG['OKX_API']['DEMO']['SECRET_KEY'],
                CONFIG['OKX_API']['DEMO']['PASSPHRASE']
            )
        else:
            trade_manager = TradeManager(
                CONFIG['OKX_API']['LIVE']['API_KEY'],
                CONFIG['OKX_API']['LIVE']['SECRET_KEY'],
                CONFIG['OKX_API']['LIVE']['PASSPHRASE'],
                CONFIG['OKX_API']['FLAG']
            )
        
        # 获取当前价格
        current_price = await get_sol_price()
        
        # 执行交易
        result = await trade_manager.place_order(
            CONFIG['TRADE']['DEFAULT_INST_ID'],
            trade_action,  # 使用存储的交易方向
            amount
        )
        
        if result['success']:
            order_data = result['data'][0]
            await update.message.reply_text(
                f"✅ 订单已提交！({trading_mode})\n\n"
                f"📊 订单信息：\n"
                f"订单ID: {order_data.get('ordId', 'Unknown')}\n"
                f"数量: {amount} SOL\n"
                f"状态: {order_data.get('state', 'Unknown')}\n"
                f"当前价格: ${current_price}",
                reply_markup=MAIN_MENU_MARKUP
            )
        else:
            await update.message.reply_text(
                f"❌ 交易失败 ({trading_mode})：{result['message']}",
                reply_markup=MAIN_MENU_MARKUP
            )
            
    except ValueError:
        await update.message.reply_text("请输入有效的数字金额")
        print("无效的输入")
    except Exception as e:
        logger.error(f"处理交易请求错误: {e}")
        await update.message.reply_text(
            "❌ 系统错误，请稍后重试",
            reply_markup=MAIN_MENU_MARKUP
        )

async def get_wallet_info(address: str) -> str:
    """
    获取钱包信息的格式化字符串
    """
    # 获取交易账户余额
    trading_balance, cash_balance, usd_value, balance_source, currency = await get_wallet_balance(address)
    
    # 判断是否为模拟盘
    is_demo = CONFIG['OKX_API']['FLAG'] == "1"
    
    # 构建基本信息
    info = [
        f"💰 交易账户余额: {trading_balance} {currency} ({balance_source})",
        f"💵 交易账户估值: ${usd_value} ({balance_source})"
    ]
    
    # 只在实盘环境下显示资金账户信息
    if not is_demo:
        # 获取资金账户余额
        funding_balance, available, frozen, f_balance_source, f_currency = await get_funding_balance(address)
        
        info.extend([
            f"💳 资金账户余额: {funding_balance} {f_currency} ({f_balance_source})",
            f"💵 资金账户估值: {'OKX资金账户暂不提供估值，可用交易账户参考！'}",
            "━━━━━━━━━━━━━━",
            f"💳 资金账户总余额: {funding_balance} {f_currency} ({f_balance_source})",
            f"💵 可用余额: {available} {f_currency} ({f_balance_source})",
            f"💵 冻结余额: {frozen} {f_currency} ({f_balance_source})"
        ])
    
    # 添加更新时间
    current_time = datetime.now().strftime("%H:%M:%S")
    info.append(f"🕒 更新时间: {current_time}")
    
    return "\n".join(info)

async def check_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理查询当前币价的回调函数
    """
    query = update.callback_query
    await query.answer()  # 响应回调查询
    
    try:
        # 获取当前价格
        current_price = await get_sol_price_okx()
        
        if current_price > 0:
            # 获取价格成功
            trading_mode = "模拟盘" if CONFIG['OKX_API']['FLAG'] == '1' else "实盘"
            await query.message.reply_text(
                f"💲 SOL 当前价格 ({trading_mode})：\n\n"
                f"📊 ${current_price:.2f} USDT\n\n"
                f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=MAIN_MENU_MARKUP
            )
        else:
            # 获取价格失败
            await query.message.reply_text(
                "❌ 获取价格失败，请稍后重试",
                reply_markup=MAIN_MENU_MARKUP
            )
    except Exception as e:
        logger.error(f"获取价格时出错: {e}")
        await query.message.reply_text(
            "❌ 系统错误，请稍后重试",
            reply_markup=MAIN_MENU_MARKUP
        )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        if query.data == "current_wallet":
            if user_id in user_wallets:
                wallet = user_wallets[user_id]
                await query.message.reply_text(
                    "请输入要查询的币种代码（默认为SOL）：\n"
                    "例如：\n"
                    "SOL - Solana\n"
                    "BTC - 比特币\n"
                    "ETH - 以太坊\n"
                    "\n直接输入币种代码，或直接点击菜单按钮返回"
                )
                context.user_data['state'] = 'waiting_for_crypto_balance'
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
            # 设置用户状态为买入
            context.user_data['trade_action'] = 'buy'
            await query.message.reply_text(
                "💰 请输入要购买的 SOL 数量：\n\n"
                f"• 最小数量：{CONFIG['TRADE']['MIN_AMOUNT']} SOL\n"
                f"• 最大数量：{CONFIG['TRADE']['MAX_AMOUNT']} SOL\n"
                "• 使用市价单执行\n\n"
                "请直接输入数字金额："
            )
            
        elif query.data == "sell":
            # 设置用户状态为卖出
            context.user_data['trade_action'] = 'sell'
            await query.message.reply_text(
                "💱 请输入要出售的 SOL 数量：\n\n"
                f"• 最小数量：{CONFIG['TRADE']['MIN_AMOUNT']} SOL\n"
                f"• 最大数量：{CONFIG['TRADE']['MAX_AMOUNT']} SOL\n"
                "• 使用市价单执行\n\n"
                "请直接输入数字金额："
            )
        elif query.data == "check_price":
            await check_price_callback(update, context)
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

        # 定义 Telegram Bot 的消息处理器列表
        handlers = [
            # 处理 /start 命令的处理器
            # 当用户发送 /start 命令时，调用 start 函数显示欢迎消息和主菜单
            CommandHandler("start", start),
            
            # 处理按钮点击事件的处理器
            # 当用户点击内联键盘按钮时，调用 handle_button 函数处理相应操作
            CallbackQueryHandler(handle_button),
            
            # 处理普通文本消息的处理器（不包括命令）
            # filters.TEXT 表示只处理文本消息
            # ~filters.COMMAND 表示排除命令消息
            # 用于处理用户输入的钱包地址和交易数量等信息
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            
            # 处理所有类型消息的处理器
            # 用于调试目的，可以捕获并记录所有消息
            MessageHandler(filters.ALL, debug_handler),
            
            # 处理价格查询回调
            CallbackQueryHandler(check_price_callback, pattern="^check_price$")
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
    """
    主程序入口点
    
    功能：
        - 启动 Telegram 机器人
        - 使用 asyncio.run() 运行异步主函数
        - 处理键盘中断信号（Ctrl+C）优雅退出
    
    异常处理：
        - 捕获 KeyboardInterrupt 异常，实现优雅退出
        - 在退出时打印提示信息
    """
    try:
        asyncio.run(main())  # 运行异步主函数
    except KeyboardInterrupt:
        print("\n收到退出信号，机器人已停止")  # 处理 Ctrl+C 退出信号
