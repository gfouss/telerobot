# 标准库导入
import asyncio
import json
import logging
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
    },
    'TRADE': {
        'DEFAULT_INST_ID': 'SOL-USDT-SWAP',  # 默认交易对
        'MIN_AMOUNT': 0.1,                    # 最小交易数量
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

async def get_wallet_balance(address: str) -> tuple:
    """
    使用OKX API 获取指定钱包地址的余额信息
    
    参数:
        address (str): Solana 钱包地址
        
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
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
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
        currency = 'UNKNOWN'  # 添加币种信息
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                sol_detail = next((detail for detail in details if detail.get('ccy') == 'SOL'), None)
                if sol_detail:
                    trading_balance = float(sol_detail.get('availBal', 0))  # 交易账户可用余额
                    cash_balance = float(sol_detail.get('cashBal', 0))   # 币种余额
                    usd_value = float(sol_detail.get('eqUsd', 0))
                    currency = sol_detail.get('ccy', 'UNKNOWN')  # 获取币种信息
                    break
        
        return (round(trading_balance, 4), round(cash_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')


async def get_funding_balance(address: str) -> tuple:
    """
    获取资金账户余额信息
    
    参数:
        address (str): Solana 钱包地址
        
    返回:
        tuple: 包含以下信息的元组:
            - balance (float): 总余额
            - available (float): 可用余额
            - frozen (float): 冻结余额
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化OKX Funding API
        fundingAPI = Funding.FundingAPI(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取资金账户余额
        result = fundingAPI.get_balances()
        
        # 保存资金账户余额到文件
        with open('funding_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        balance = 0.0
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'
        
        if isinstance(result, dict) and result.get('code') == '0':
            for balance_data in result.get('data', []):
                if balance_data.get('ccy') == 'SOL':
                    balance = float(balance_data.get('bal', 0))
                    available = float(balance_data.get('availBal', 0))
                    frozen = float(balance_data.get('frozenBal', 0))
                    currency = balance_data.get('ccy', 'UNKNOWN')
                    break
        
        return (round(balance, 4), round(available, 4), round(frozen, 4), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX资金账户信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')

async def get_sol_price_okx() -> float:
    """
    从 OKX 交易所获取 SOL 当前价格
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{CONFIG['OKX_API']['BASE_URL']}/api/v5/market/ticker"
            params = {'instId': 'SOL-USDT-SWAP'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"OKX API 错误: 状态码 {response.status}")
                    return 0.0
                
                data = await response.json()
                if data.get('code') == '0' and data.get('data'):
                    ticker_data = data['data'][0]
                    mark_price = float(ticker_data.get('markPx', 0))
                    last_price = float(ticker_data.get('last', 0))
                    if mark_price == 0 and last_price == 0:
                        logger.error("OKX API 返回价格为0")
                        return 0.0
                    return mark_price or last_price
                
                logger.error(f"OKX API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        logger.error(f"获取 OKX 价格错误: {str(e)}")
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
    
    功能:
        - 处理钱包地址验证
        - 处理交易数量输入
        - 执行买入/卖出操作
    
    参数:
        update (Update): Telegram 更新对象
        context (ContextTypes.DEFAULT_TYPE): 回调上下文
    """
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
        
        # 验证数量是否在允许范围内
        if amount < CONFIG['TRADE']['MIN_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太小，最小交易数量为 {CONFIG['TRADE']['MIN_AMOUNT']}")
            return
            
        if amount > CONFIG['TRADE']['MAX_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太大，最大交易数量为 {CONFIG['TRADE']['MAX_AMOUNT']}")
            return
        
        # 获取交易方向
        trade_action = context.user_data.get('trade_action', 'buy')  # 默认为买入
        
        # 执行交易
        trade_manager = TradeManager(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
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
                f"✅ 订单已提交！\n\n"
                f"📊 订单信息：\n"
                f"订单ID: {order_data.get('ordId', 'Unknown')}\n"
                f"数量: {amount} SOL\n"
                f"状态: {order_data.get('state', 'Unknown')}\n"
                f"当前价格: ${current_price}",
                reply_markup=MAIN_MENU_MARKUP
            )
        else:
            await update.message.reply_text(
                f"❌ 交易失败：{result['message']}",
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

async def get_wallet_balance(address: str) -> tuple:
    """
    获取指定钱包地址的余额信息
    
    参数:
        address (str): Solana 钱包地址
        
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
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取账户余额
        result = accountAPI.get_account_balance()
        
        # 保存账户余额到文件
        with open('trading_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        trading_balance = 0.0  # 交易账户余额
        cash_balance = 0.0  # 币种余额
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'  # 添加币种信息
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                sol_detail = next((detail for detail in details if detail.get('ccy') == 'SOL'), None)
                if sol_detail:
                    trading_balance = float(sol_detail.get('availBal', 0))  # 交易账户可用余额
                    cash_balance = float(sol_detail.get('cashBal', 0))   # 币种余额
                    usd_value = float(sol_detail.get('eqUsd', 0))
                    currency = sol_detail.get('ccy', 'UNKNOWN')  # 获取币种信息
                    break
        
        return (round(trading_balance, 4), round(cash_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')


async def get_funding_balance(address: str) -> tuple:
    """
    获取资金账户余额信息
    
    参数:
        address (str): Solana 钱包地址
        
    返回:
        tuple: 包含以下信息的元组:
            - balance (float): 总余额
            - available (float): 可用余额
            - frozen (float): 冻结余额
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化OKX Funding API
        fundingAPI = Funding.FundingAPI(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取资金账户余额
        result = fundingAPI.get_balances()
        
        # 保存资金账户余额到文件
        with open('funding_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        balance = 0.0
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'
        
        if isinstance(result, dict) and result.get('code') == '0':
            for balance_data in result.get('data', []):
                if balance_data.get('ccy') == 'SOL':
                    balance = float(balance_data.get('bal', 0))
                    available = float(balance_data.get('availBal', 0))
                    frozen = float(balance_data.get('frozenBal', 0))
                    currency = balance_data.get('ccy', 'UNKNOWN')
                    break
        
        return (round(balance, 4), round(available, 4), round(frozen, 4), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX资金账户信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')

async def get_sol_price_okx() -> float:
    """
    从 OKX 交易所获取 SOL 当前价格
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{CONFIG['OKX_API']['BASE_URL']}/api/v5/market/ticker"
            params = {'instId': 'SOL-USDT-SWAP'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"OKX API 错误: 状态码 {response.status}")
                    return 0.0
                
                data = await response.json()
                if data.get('code') == '0' and data.get('data'):
                    ticker_data = data['data'][0]
                    mark_price = float(ticker_data.get('markPx', 0))
                    last_price = float(ticker_data.get('last', 0))
                    if mark_price == 0 and last_price == 0:
                        logger.error("OKX API 返回价格为0")
                        return 0.0
                    return mark_price or last_price
                
                logger.error(f"OKX API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        logger.error(f"获取 OKX 价格错误: {str(e)}")
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
    从文件加载用户钱包数据
    
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
    保存用户钱包数据到文件
    
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
    
    功能:
        - 处理钱包地址验证
        - 处理交易数量输入
        - 执行买入/卖出操作
    
    参数:
        update (Update): Telegram 更新对象
        context (ContextTypes.DEFAULT_TYPE): 回调上下文
    """
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
        
        # 验证数量是否在允许范围内
        if amount < CONFIG['TRADE']['MIN_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太小，最小交易数量为 {CONFIG['TRADE']['MIN_AMOUNT']}")
            return
            
        if amount > CONFIG['TRADE']['MAX_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太大，最大交易数量为 {CONFIG['TRADE']['MAX_AMOUNT']}")
            return
        
        # 获取交易方向
        trade_action = context.user_data.get('trade_action', 'buy')  # 默认为买入
        
        # 执行交易
        trade_manager = TradeManager(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
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
                f"✅ 订单已提交！\n\n"
                f"📊 订单信息：\n"
                f"订单ID: {order_data.get('ordId', 'Unknown')}\n"
                f"数量: {amount} SOL\n"
                f"状态: {order_data.get('state', 'Unknown')}\n"
                f"当前价格: ${current_price}",
                reply_markup=MAIN_MENU_MARKUP
            )
        else:
            await update.message.reply_text(
                f"❌ 交易失败：{result['message']}",
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

async def get_wallet_balance(address: str) -> tuple:
    """
    获取指定钱包地址的余额信息
    
    参数:
        address (str): Solana 钱包地址
        
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
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取账户余额
        result = accountAPI.get_account_balance()
        
        # 保存账户余额到文件
        with open('trading_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        trading_balance = 0.0  # 交易账户余额
        cash_balance = 0.0  # 币种余额
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'  # 添加币种信息
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                sol_detail = next((detail for detail in details if detail.get('ccy') == 'SOL'), None)
                if sol_detail:
                    trading_balance = float(sol_detail.get('availBal', 0))  # 交易账户可用余额
                    cash_balance = float(sol_detail.get('cashBal', 0))   # 币种余额
                    usd_value = float(sol_detail.get('eqUsd', 0))
                    currency = sol_detail.get('ccy', 'UNKNOWN')  # 获取币种信息
                    break
        
        return (round(trading_balance, 4), round(cash_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')


async def get_funding_balance(address: str) -> tuple:
    """
    获取资金账户余额信息
    
    参数:
        address (str): Solana 钱包地址
        
    返回:
        tuple: 包含以下信息的元组:
            - balance (float): 总余额
            - available (float): 可用余额
            - frozen (float): 冻结余额
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化OKX Funding API
        fundingAPI = Funding.FundingAPI(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取资金账户余额
        result = fundingAPI.get_balances()
        
        # 保存资金账户余额到文件
        with open('funding_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        balance = 0.0
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'
        
        if isinstance(result, dict) and result.get('code') == '0':
            for balance_data in result.get('data', []):
                if balance_data.get('ccy') == 'SOL':
                    balance = float(balance_data.get('bal', 0))
                    available = float(balance_data.get('availBal', 0))
                    frozen = float(balance_data.get('frozenBal', 0))
                    currency = balance_data.get('ccy', 'UNKNOWN')
                    break
        
        return (round(balance, 4), round(available, 4), round(frozen, 4), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX资金账户信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')

async def get_sol_price_okx() -> float:
    """
    从 OKX 交易所获取 SOL 当前价格
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{CONFIG['OKX_API']['BASE_URL']}/api/v5/market/ticker"
            params = {'instId': 'SOL-USDT-SWAP'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"OKX API 错误: 状态码 {response.status}")
                    return 0.0
                
                data = await response.json()
                if data.get('code') == '0' and data.get('data'):
                    ticker_data = data['data'][0]
                    mark_price = float(ticker_data.get('markPx', 0))
                    last_price = float(ticker_data.get('last', 0))
                    if mark_price == 0 and last_price == 0:
                        logger.error("OKX API 返回价格为0")
                        return 0.0
                    return mark_price or last_price
                
                logger.error(f"OKX API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        logger.error(f"获取 OKX 价格错误: {str(e)}")
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
    从文件加载用户钱包数据
    
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
    保存用户钱包数据到文件
    
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
    
    功能:
        - 处理钱包地址验证
        - 处理交易数量输入
        - 执行买入/卖出操作
    
    参数:
        update (Update): Telegram 更新对象
        context (ContextTypes.DEFAULT_TYPE): 回调上下文
    """
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
        
        # 验证数量是否在允许范围内
        if amount < CONFIG['TRADE']['MIN_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太小，最小交易数量为 {CONFIG['TRADE']['MIN_AMOUNT']}")
            return
            
        if amount > CONFIG['TRADE']['MAX_AMOUNT']:
            await update.message.reply_text(f"❌ 数量太大，最大交易数量为 {CONFIG['TRADE']['MAX_AMOUNT']}")
            return
        
        # 获取交易方向
        trade_action = context.user_data.get('trade_action', 'buy')  # 默认为买入
        
        # 执行交易
        trade_manager = TradeManager(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
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
                f"✅ 订单已提交！\n\n"
                f"📊 订单信息：\n"
                f"订单ID: {order_data.get('ordId', 'Unknown')}\n"
                f"数量: {amount} SOL\n"
                f"状态: {order_data.get('state', 'Unknown')}\n"
                f"当前价格: ${current_price}",
                reply_markup=MAIN_MENU_MARKUP
            )
        else:
            await update.message.reply_text(
                f"❌ 交易失败：{result['message']}",
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

async def get_wallet_balance(address: str) -> tuple:
    """
    获取指定钱包地址的余额信息
    
    参数:
        address (str): Solana 钱包地址
        
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
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取账户余额
        result = accountAPI.get_account_balance()
        
        # 保存账户余额到文件
        with open('trading_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        trading_balance = 0.0  # 交易账户余额
        cash_balance = 0.0  # 币种余额
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'  # 添加币种信息
        
        if isinstance(result, dict) and result.get('code') == '0':
            for account_data in result.get('data', []):
                details = account_data.get('details', [])
                sol_detail = next((detail for detail in details if detail.get('ccy') == 'SOL'), None)
                if sol_detail:
                    trading_balance = float(sol_detail.get('availBal', 0))  # 交易账户可用余额
                    cash_balance = float(sol_detail.get('cashBal', 0))   # 币种余额
                    usd_value = float(sol_detail.get('eqUsd', 0))
                    currency = sol_detail.get('ccy', 'UNKNOWN')  # 获取币种信息
                    break
        
        return (round(trading_balance, 4), round(cash_balance, 4), round(usd_value, 2), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX钱包信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')


async def get_funding_balance(address: str) -> tuple:
    """
    获取资金账户余额信息
    
    参数:
        address (str): Solana 钱包地址
        
    返回:
        tuple: 包含以下信息的元组:
            - balance (float): 总余额
            - available (float): 可用余额
            - frozen (float): 冻结余额
            - balance_source (str): 余额来源
            - currency (str): 货币类型
    """
    try:
        # 初始化OKX Funding API
        fundingAPI = Funding.FundingAPI(
            CONFIG['OKX_API']['API_KEY'],
            CONFIG['OKX_API']['SECRET_KEY'],
            CONFIG['OKX_API']['PASSPHRASE'],
            False,
            CONFIG['OKX_API']['FLAG']
        )
        
        # 获取资金账户余额
        result = fundingAPI.get_balances()
        
        # 保存资金账户余额到文件
        with open('funding_balance.txt', 'w') as file:
            json.dump(result, file, indent=4)
        
        # 解析余额信息
        balance = 0.0
        usd_value = 0.0
        balance_source = 'OKX'
        currency = 'UNKNOWN'
        
        if isinstance(result, dict) and result.get('code') == '0':
            for balance_data in result.get('data', []):
                if balance_data.get('ccy') == 'SOL':
                    balance = float(balance_data.get('bal', 0))
                    available = float(balance_data.get('availBal', 0))
                    frozen = float(balance_data.get('frozenBal', 0))
                    currency = balance_data.get('ccy', 'UNKNOWN')
                    break
        
        return (round(balance, 4), round(available, 4), round(frozen, 4), balance_source, currency)
            
    except Exception as e:
        logger.error(f"获取OKX资金账户信息错误: {e}")
        return (0.0, 0.0, 0.0, 'Unknown', 'UNKNOWN')

async def get_sol_price_okx() -> float:
    """
    从 OKX 交易所获取 SOL 当前价格
    
    返回:
        float: SOL 当前价格，如果获取失败返回 0.0
    """
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{CONFIG['OKX_API']['BASE_URL']}/api/v5/market/ticker"
            params = {'instId': 'SOL-USDT-SWAP'}
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"OKX API 错误: 状态码 {response.status}")
                    return 0.0
                
                data = await response.json()
                if data.get('code') == '0' and data.get('data'):
                    ticker_data = data['data'][0]
                    mark_price = float(ticker_data.get('markPx', 0))
                    last_price = float(ticker_data.get('last', 0))
                    if mark_price == 0 and last_price == 0:
                        logger.error("OKX API 返回价格为0")
                        return 0.0
                    return mark_price or last_price
                
                logger.error(f"OKX API 响应格式错误: {data}")
                return 0.0
    except Exception as e:
        logger.error(f"获取 OKX 价格错误: {str(e)}")
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
    从文件加载用户钱包数据
    
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
    保存用户钱包数据到文件
    
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

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        if query.data == "current_wallet":
            if user_id in user_wallets:
                wallet = user_wallets[user_id]
                trading_balance, trading_cash_balance, trading_usd_value, trading_balance_source, trading_currency = await get_wallet_balance(wallet)
                funding_balance, funding_available, funding_frozen, funding_source, funding_currency = await get_funding_balance(wallet)

                new_text = (
                    f"📱 当前连接的钱包信息：\n\n"
                    f"📍 地址: {wallet}\n"
                    f"💰 交易账户余额: {trading_balance} {trading_currency} ({trading_balance_source})\n"
                    f"💵 交易账户估值: ${trading_usd_value} ({trading_balance_source})\n"
                    f"💳 资金账户余额: {trading_cash_balance} {trading_currency} ({trading_balance_source})\n"
                    f"💵 资金账户估值: OKX资金账户暂不提供估值，可用交易账户参考！\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💳 资金账户总余额: {funding_balance} {funding_currency} ({funding_source})\n"
                    f"💵 可用余额: {funding_available} {funding_currency} ({funding_source})\n"
                    f"💵 冻结余额: {funding_frozen} {funding_currency} ({funding_source})\n"
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

