from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from decimal import Decimal
import logging
import asyncio  # 添加这行

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # 改为 INFO 级别
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TOKEN = "7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA"

# 交易相关的按钮和菜单
TRADE_MENU = """
<b>Solana 交易助手</b>

请选择您要进行的操作：
"""

# 键盘布局
MAIN_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("💰 购买代币", callback_data="buy")],
    [InlineKeyboardButton("💱 出售代币", callback_data="sell")],
    [InlineKeyboardButton("📊 查看余额", callback_data="balance")],
    [InlineKeyboardButton("⚙️ 设置", callback_data="settings")]
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的 /start 命令")
    try:
        # 先发送欢迎消息
        await update.message.reply_text(
            "👋 欢迎使用 Solana 交易助手！\n\n"
            "我可以帮助您：\n"
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

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理按钮点击"""
    query = update.callback_query
    await query.answer()

    if query.data == "buy":
        await query.message.reply_text("请输入要购买的代币数量：")
    elif query.data == "sell":
        await query.message.reply_text("请输入要出售的代币数量：")
    elif query.data == "balance":
        # 这里添加查询余额的逻辑
        await query.message.reply_text("正在查询余额...")
    elif query.data == "settings":
        await query.message.reply_text("设置功能开发中...")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户输入的消息"""
    user = update.effective_user
    text = update.message.text
    print(f"\n收到来自用户 {user.first_name}({user.id}) 的消息: {text}")
    
    try:
        amount = Decimal(text)
        # 这里添加处理具体金额的逻辑
        await update.message.reply_text(f"收到金额：{amount}\n处理中...")
        print(f"处理金额: {amount}")
    except:
        await update.message.reply_text("请输入有效的数字金额")
        print("无效的金额输入")

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

async def main():
    """启动机器人"""
    print('\n=== Solana 交易助手 ===')
    print('正在初始化...')
    
    try:
        # 测试 Token 是否有效
        print(f'正在验证 Token...')
        app = (
            Application.builder()
            .token(TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .get_updates_read_timeout(30)
            .get_updates_connection_pool_size(100)
            .http_version("1.1")
            .build()
        )

        print('正在配置处理程序...')
        # 调整处理器顺序
        print('• 注册 /start 命令处理器')
        app.add_handler(CommandHandler("start", start))
        
        print('• 注册按钮处理器')
        app.add_handler(CallbackQueryHandler(handle_button))
        
        print('• 注册普通消息处理器')
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print('• 注册调试处理器')
        app.add_handler(MessageHandler(filters.ALL, debug_handler))
        
        # 添加错误处理
        app.add_error_handler(error)
        
        print('所有处理程序注册完成')

        print('启动机器人...')
        async with app:
            print('正在连接到 Telegram 服务器...')
            await app.initialize()
            await app.start()  # 添加这行
            print('连接成功！')
            
            # 发送启动消息到 Telegram
            bot = app.bot
            await bot.send_message(
                chat_id=7792247162,  # 替换为你的聊天 ID
                text="🚀 Solana 交易助手已启动！\n\n发送 /start 开始交易"
            )
            
            print('\n机器人已成功启动！')
            print('在 Telegram 中发送 /start 开始使用')
            print('按 Ctrl+C 可停止机器人\n')
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
    except Exception as e:
        print(f'\n错误: {e}')
        print('请检查：')
        print('1. Token 是否正确')
        print('2. 网络连接是否正常')
        print('3. 是否已在 BotFather 中正确创建机器人')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n收到退出信号，机器人已停止")