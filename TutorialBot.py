import logging

# 导入所需的 Telegram Bot API 组件
from telegram import Update, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler

# 配置日志记录器
logger = logging.getLogger(__name__)

# 存储机器人的大写模式状态
screaming = False

# 预定义菜单文本内容
FIRST_MENU = "<b>Menu 1</b>\n\nA beautiful menu with a shiny inline button."
SECOND_MENU = "<b>Menu 2</b>\n\nA better menu with even more shiny inline buttons."

# 预定义按钮文本
NEXT_BUTTON = "Next"
BACK_BUTTON = "Back"
TUTORIAL_BUTTON = "Tutorial"

# 构建内联键盘布局
# 第一个菜单只包含一个"下一页"按钮
FIRST_MENU_MARKUP = InlineKeyboardMarkup([[
    InlineKeyboardButton(NEXT_BUTTON, callback_data=NEXT_BUTTON)
]])
# 第二个菜单包含"返回"按钮和"教程"链接
SECOND_MENU_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton(BACK_BUTTON, callback_data=BACK_BUTTON)],
    [InlineKeyboardButton(TUTORIAL_BUTTON, url="https://core.telegram.org/bots/api")]
])


async def echo(update: Update, context: CallbackContext) -> None:
    """
    消息回显处理函数
    - 如果处于大写模式，将消息转换为大写后发送
    - 否则直接复制用户的消息
    """
    # 在控制台打印用户消息
    print(f'{update.message.from_user.first_name} wrote {update.message.text}')

    if screaming and update.message.text:
        # 大写模式：将消息转换为大写
        await context.bot.send_message(
            update.message.chat_id,
            update.message.text.upper(),
            # 保留原始消息的格式实体（加粗、斜体等）
            entities=update.message.entities
        )
    else:
        # 普通模式：直接复制消息
        await update.message.copy(update.message.chat_id)


def scream(update: Update, context: CallbackContext) -> None:
    """
    处理 /scream 命令
    开启大写模式
    """
    global screaming
    screaming = True


def whisper(update: Update, context: CallbackContext) -> None:
    """
    处理 /whisper 命令
    关闭大写模式
    """
    global screaming
    screaming = False


def menu(update: Update, context: CallbackContext) -> None:
    """
    处理 /menu 命令
    显示带有内联按钮的交互菜单
    """
    context.bot.send_message(
        update.message.from_user.id,
        FIRST_MENU,
        parse_mode=ParseMode.HTML,
        reply_markup=FIRST_MENU_MARKUP
    )


def button_tap(update: Update, context: CallbackContext) -> None:
    """
    处理菜单按钮的点击事件
    根据按钮类型切换不同的菜单视图
    """
    # 获取按钮的回调数据
    data = update.callback_query.data
    text = ''
    markup = None

    # 根据按钮类型选择对应的菜单内容
    if data == NEXT_BUTTON:
        text = SECOND_MENU
        markup = SECOND_MENU_MARKUP
    elif data == BACK_BUTTON:
        text = FIRST_MENU
        markup = FIRST_MENU_MARKUP

    # 响应按钮点击，结束加载动画
    update.callback_query.answer()

    # 更新消息内容，显示新的菜单
    update.callback_query.message.edit_text(
        text,
        ParseMode.HTML,
        reply_markup=markup
    )


def main() -> None:
    # 创建机器人应用实例
    app = Application.builder().token("7962892675:AAHpTzi_MHNcO3coYyJMN3lQ7I3fYJMGdEA").build()

    # 注册命令处理器
    app.add_handler(CommandHandler("scream", scream))
    app.add_handler(CommandHandler("whisper", whisper))
    app.add_handler(CommandHandler("menu", menu))

    # 注册按钮回调处理器
    app.add_handler(CallbackQueryHandler(button_tap))

    # 注册消息回显处理器（处理所有非命令消息）
    app.add_handler(MessageHandler(~filters.COMMAND, echo))

    # 启动机器人
    print('机器人启动中...')
    app.run_polling()


# 程序入口点
if __name__ == '__main__':
    main()