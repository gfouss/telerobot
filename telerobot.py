from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 替换为你的bot token
TOKEN = "7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    await update.message.reply_text('你好！我是一个自动回复机器人。')

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
    # 创建应用
    app = Application.builder().token(TOKEN).build()

    # 添加处理程序
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # 添加错误处理
    app.add_error_handler(error)
    
    # 开始轮询
    print('机器人启动中...')
    await app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())