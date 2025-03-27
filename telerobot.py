from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# 替换为你的bot token
TOKEN = "7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    await update.message.reply_text(
        "👋 你好！我是一个自动回复机器人。\n\n"
        "🤖 我可以：\n"
        "• 回复你发送的任何消息\n"
        "• 使用 /help 获取帮助\n\n"
        "✨ 请开始聊天！"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    await update.message.reply_text('发送任何消息，我都会回复你！')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户发送的消息"""
    message_type = update.message.chat.type
    text = update.message.text

    # 打印接收到的消息
    print(f'用户 ({update.message.chat.id}) 在 {message_type} 中说: "{text}"')

    # 这里可以自定义回复逻辑
    response = f"你说的是: {text}"
    
    await update.message.reply_text(response)

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    print(f'Update {update} caused error {context.error}')

async def main():
    print('\n=== Telegram 自动回复机器人 ===')
    print('正在初始化...')
    
    # 创建应用
    print('正在配置应用...')
    app = (
        Application.builder()
        .token(TOKEN)
        .connect_timeout(10)
        .read_timeout(10)
        .pool_timeout(10)
        .get_updates_read_timeout(10)
        .write_timeout(10)
        .build()
    )

    # 添加处理程序
    print('正在注册命令处理程序...')
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_error_handler(error)
    
    # 开始轮询
    print('\n机器人启动信息：')
    print(f'• Token: {TOKEN}')
    print('• 命令列表：')
    print('  - /start : 开始使用')
    print('  - /help  : 获取帮助')
    print('\n正在启动机器人...')
    
    await app.initialize()
    await app.start()
    try:
        print('\n机器人已成功启动！')
        print('在 Telegram 中发送 /start 开始使用')
        print('按 Ctrl+C 可停止机器人\n')
        await app.updater.start_polling()
        await asyncio.Event().wait()
    finally:
        await app.stop()

if __name__ == '__main__':
    asyncio.run(main())