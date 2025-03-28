# 标准库导入
import asyncio  # 用于异步操作
import json    # 用于处理 JSON 数据
import logging # 用于日志记录
import ssl     # 用于 SSL/TLS 安全连接
from decimal import Decimal  # 用于精确的十进制计算

# 第三方库导入
import aiohttp  # 用于异步 HTTP 请求
import base58   # 用于 Base58 编码/解码
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton  # Telegram Bot API 组件
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters  # Telegram Bot 处理器

# 配置常量
CONFIG = {
    'TOKEN': "7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA",  # Telegram Bot Token
    'SOLANA_RPC_URLS': {  # Solana 网络 RPC 节点
        'mainnet': "https://api.mainnet-beta.solana.com",  # 主网
        'testnet': "https://api.testnet.solana.com",       # 测试网
        'devnet': "https://api.devnet.solana.com"          # 开发网
    },
    'CURRENT_NETWORK': 'devnet',  # 当前使用的网络
    'COINGECKO_API_URL': "https://api.coingecko.com/api/v3",  # CoinGecko API 地址
    'ADMIN_CHAT_ID': 7792247162,  # 管理员的 Telegram ID
    'WALLET_FILE': "wallets.json"  # 钱包数据存储文件
}

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 交易相关的按钮和菜单
TRADE_MENU = """
<b>Solana 交易助手</b>

请选择您要进行的操作：
"""

# 键盘布局
# 修改键盘布局，添加钱包连接按钮
MAIN_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔗 连接钱包", callback_data="connect_wallet")],
    [InlineKeyboardButton("👛 当前钱包", callback_data="current_wallet")],  # 新增
    [InlineKeyboardButton("💰 购买代币", callback_data="buy")],
    [InlineKeyboardButton("💱 出售代币", callback_data="sell")],
    [InlineKeyboardButton("📊 查看余额", callback_data="balance")],
    [InlineKeyboardButton("⚙️ 设置", callback_data="settings")]
])

# 修改 handle_button 函数，添加钱包连接处理
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        # 先尝试应答回调查询
        await query.answer()
        
        if query.data == "current_wallet":
            if user_id in user_wallets:
                wallet = user_wallets[user_id]
                balance, usd_value = await get_wallet_balance(wallet)
                
                # 构造新消息
                new_text = (
                    f"📱 当前连接的钱包信息：\n\n"
                    f"📍 地址: {wallet}\n"
                    f"💰 余额: {balance}\n"
                    f"💵 估值: {usd_value} USD"
                )
                
                try:
                    await query.message.edit_text(
                        new_text,
                        reply_markup=MAIN_MENU_MARKUP
                    )
                except Exception as e:
                    if "message is not modified" in str(e).lower():
                        await query.answer("✅ 钱包信息已是最新")
                    else:
                        print(f"更新消息错误: {e}")
                        await query.message.reply_text(MAIN_MENU_MARKUP)
            else:
                try:
                    await query.message.edit_text(
                        "❌ 还未连接钱包！\n"
                        "请点击「🔗 连接钱包」按钮进行连接。",
                        reply_markup=MAIN_MENU_MARKUP
                    )
                except Exception as e:
                    if "message is not modified" in str(e).lower():
                        await query.answer("请先连接钱包")
                    else:
                        print(f"更新消息错误: {e}")
                        await query.message.reply_text(
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
        elif query.data == "balance":
            await query.message.reply_text("正在查询余额...")
        elif query.data == "settings":
            await query.message.reply_text("设置功能开发中...")
            
    except Exception as e:
        print(f"处理按钮点击错误: {e}")
        if "query is too old" in str(e).lower():
            await update.effective_chat.send_message(
                "⚠️ 操作超时，请重新点击按钮",
                reply_markup=MAIN_MENU_MARKUP
            )

# 修改消息处理函数，添加钱包地址验证
# 添加用户钱包存储
user_wallets = {}  # 用户ID -> 钱包地址的映射

# 修改消息处理函数中的钱包验证部分
# 添加导入
# 移除这些导入
# from solana.rpc.api import Client
# from solana.publickey import PublicKey
# from web3 import Web3

# 移除 Web3 初始化
# w3 = Web3(Web3.HTTPProvider(SOLANA_RPC_URL))

# 修改地址验证函数
def is_valid_solana_address(address: str) -> bool:
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except:
        return False

# 修改余额查询函数
async def get_wallet_balance(wallet_address: str) -> tuple:
    """
    查询指定钱包地址的 SOL 余额
    
    Args:
        wallet_address: Solana 钱包地址
        
    Returns:
        tuple: (余额字符串, USD 估值字符串)
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",  # 模拟浏览器请求
            "Accept": "application/json"   # 指定接受 JSON 响应
        }
        
        # 增加超时时间
        timeout = aiohttp.ClientTimeout(total=15, connect=10)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        rpc_url = CONFIG['SOLANA_RPC_URLS'][CONFIG['CURRENT_NETWORK']]
        print(f"正在查询余额，网络: {CONFIG['CURRENT_NETWORK']}, RPC: {rpc_url}")
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(rpc_url, 
                                    json=payload,
                                    headers=headers,
                                    ssl=ssl_context) as response:
                    if response.status != 200:
                        print(f"RPC 请求失败，状态码: {response.status}")
                        return "查询失败 (HTTP错误)", "N/A"
                    
                    response_text = await response.text()
                    print(f"原始响应: {response_text}")
                    
                    data = await response.json()
                    print(f"RPC 响应: {data}")
                    
                    if "error" in data:
                        print(f"RPC 返回错误: {data['error']}")
                        return "查询失败 (RPC错误)", "N/A"
                    
                    if "result" in data and "value" in data["result"]:
                        balance_lamports = int(data["result"]["value"])
                        balance_sol = balance_lamports / 1_000_000_000
                        
                        sol_price = await get_sol_price()
                        print(f"SOL 价格: ${sol_price}")
                        
                        usd_value = balance_sol * sol_price
                        
                        balance_sol = Decimal(str(balance_sol))
                        usd_value = Decimal(str(usd_value))
                        
                        return f"{balance_sol:.9f} SOL ({CONFIG['CURRENT_NETWORK']})", f"${usd_value:.2f}"
                    else:
                        print(f"无效的 RPC 响应格式: {data}")
                        return f"0.000000000 SOL ({CONFIG['CURRENT_NETWORK']})", "$0.00"
            except asyncio.TimeoutError:
                print("RPC 请求超时")
                return "查询失败 (请求超时)", "N/A"
            except Exception as e:
                print(f"RPC 请求错误: {e}")
                return "查询失败 (请求错误)", "N/A"
    except Exception as e:
        print(f"查询余额错误: {str(e)}")
        return "查询失败", "N/A"

# 添加价格查询配置
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# 添加价格查询函数
async def get_sol_price() -> float:
    """
    从 CoinGecko 获取 SOL 当前价格
    
    Returns:
        float: SOL 的 USD 价格
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{COINGECKO_API_URL}/simple/price",
                params={
                    "ids": "solana",
                    "vs_currencies": "usd"
                }
            ) as response:
                data = await response.json()
                return data["solana"]["usd"]
    except Exception as e:
        print(f"获取价格错误: {e}")
        return 0.0

# 修改消息处理函数中的钱包验证部分
# 添加钱包存储相关函数
# 添加钱包存储相关函数
def load_wallets():
    """从文件加载钱包数据"""
    try:
        with open(CONFIG['WALLET_FILE'], 'r') as f:
            wallets_data = json.load(f)
            # 将字符串键转换为整数键
            return {int(user_id): address for user_id, address in wallets_data.items()}
    except FileNotFoundError:
        return {}

def save_wallets(wallets):
    """保存钱包数据到文件"""
    # 将整数键转换为字符串键，因为JSON只支持字符串键
    wallets_data = {str(user_id): address for user_id, address in wallets.items()}
    with open(CONFIG['WALLET_FILE'], 'w') as f:
        json.dump(wallets_data, f)

# 修改用户钱包存储初始化
user_wallets = load_wallets()

# 修改 handle_message 函数中保存钱包的部分
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的消息: {text}")
    
    # 检查是否是钱包地址
    if is_valid_solana_address(text):
        msg = await update.message.reply_text("正在验证钱包地址...")
        
        try:
            # 查询余额
            balance, usd_value = await get_wallet_balance(text)
            # 在保存钱包地址后添加
            user_wallets[user.id] = text  # 保存钱包地址
            save_wallets(user_wallets)    # 保存到文件
            
            # 发送成功消息和余额信息
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

    # 处理其他消息
    try:
        amount = Decimal(text)
        await update.message.reply_text(f"收到金额：{amount}\n处理中...")
        print(f"处理金额: {amount}")
    except:
        await update.message.reply_text("请输入有效的数字金额或 Solana 钱包地址")
        print("无效的输入")

# 添加错误处理函数
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    print(f'发生错误: {context.error}')
    logger.error(f'Update {update} caused error {context.error}')

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
        # 继续处理消息，不中断
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的 /start 命令")
    try:
        # 先发送欢迎消息
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
        
        # 然后显示主菜单
        await update.message.reply_text(
            text=TRADE_MENU,
            parse_mode='HTML',
            reply_markup=MAIN_MENU_MARKUP
        )
        print("已发送主菜单")
    except Exception as e:
        print(f"发送菜单时出错: {e}")
        await update.message.reply_text("抱歉，显示菜单时出现错误。")

async def main():
    """启动机器人"""
    print('\n=== Solana 交易助手 ===')
    print('正在初始化...')
    
    # 加载钱包数据
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

        # 注册处理程序
        handlers = [
            CommandHandler("start", start),
            CallbackQueryHandler(handle_button),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.ALL, debug_handler)
        ]
        
        for handler in handlers:
            app.add_handler(handler)
        
        app.add_error_handler(error)
        
        print('所有处理程序注册完成')

        # 启动机器人
        async with app:
            await app.initialize()
            await app.start()
            
            # 发送启动消息
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