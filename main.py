"""imports: telegram & telegram.ext are from python-telegram-bot"""
import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, \
    CommandHandler, ContextTypes

TOKEN = '5082339803:AAGEWGKxefXXDmDepYW3waKCYyuJYSJubD0'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class Status:
    (STARTED, WAITING_FOR_NAME, WAITING_FOR_ADDRESS_HOUSE,
     WAITING_FOR_ADDRESS_ENTRANCE, WAITING_FOR_ADDRESS_FLOOR,
     WAITING_FOR_ADDRESS_FLAT, WAITING_FOR_PHONE,
     READY_NO_COMMENT, EDIT_NAME, EDIT_ADDRESS_HOUSE, EDIT_ADDRESS_ENTRANCE,
     EDIT_ADDRESS_FLOOR, EDIT_ADDRESS_FLAT, EDIT_PHONE, EDIT_COMMENT,
     READY, WAITING_FOR_PAYMENT) = range(17)


def create_connection(db_file):
    """ create a database connection to the SQLite database
        specified by db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn_ = None
    try:
        conn_ = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)

    return conn_


def create_table(conn_, create_table_sql):
    """ create a table from the create_table_sql statement
    :param conn_: Connection object
    :param create_table_sql: a CREATE TABLE statement
    :return:
    """
    try:
        c = conn_.cursor()
        c.execute(create_table_sql)
    except sqlite3.Error as e:
        print(e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    insert_user_info(update.message.chat_id)

    reply_keyboard = [['Вынести мусор']]

    await update.message.reply_html(
        'Привет!👋\n'
        'Я - бот, который поможет тебе вынести 🗑!\n'
        'Нажми на кнопку [Вынести мусор]',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
    )


async def check_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    user_info = get_user_details(update.message.chat_id)
    user_filled = user_info_filled(update.message.chat_id)[0]
    if not user_filled:
        insert_user_info(update.message.chat_id, status=Status.WAITING_FOR_NAME)
        await update.message.reply_html(
            '<b>Введите Имя:</b>'
        )
    else:
        await update.message.reply_html(
            '<b>Сохраненные данные:</b>\n\n'
            '<b><i>Имя:</i></b>\n'
            f'{user_info[0]}\n'
            '<b><i>Адрес:</i></b>\n'
            f'{user_info[1]}, {user_info[2]}, {user_info[3]}, {user_info[4]}\n'
            '<b><i>Номер телефона:</i></b>\n'
            f'{user_info[5]}\n'
            '<b><i>Комментарий:</i></b>\n'
            f'{user_info[6]}',
            reply_markup=ReplyKeyboardMarkup(
                [['Редактировать имя', 'Редактировать адрес'],
                 ['Редактировать номер', 'Редактировать комментарий'],
                 ['Оформить заказ']],
                one_time_keyboard=True
            )
        )


async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_status = get_user_status(update.message.chat_id)[0]
    match user_status:
        case Status.WAITING_FOR_NAME:
            insert_user_info(update.message.chat_id,
                             status=Status.WAITING_FOR_ADDRESS_HOUSE,
                             name=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер дома:</b>'
            )
        case Status.WAITING_FOR_ADDRESS_HOUSE:
            insert_user_info(update.message.chat_id,
                             status=Status.WAITING_FOR_ADDRESS_ENTRANCE,
                             house=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер подъезда:</b>'
            )
        case Status.WAITING_FOR_ADDRESS_ENTRANCE:
            insert_user_info(update.message.chat_id,
                             status=Status.WAITING_FOR_ADDRESS_FLOOR,
                             entrance=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер этажа:</b>'
            )
        case Status.WAITING_FOR_ADDRESS_FLOOR:
            insert_user_info(update.message.chat_id,
                             status=Status.WAITING_FOR_ADDRESS_FLAT,
                             floor=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер квартиры:</b>'
            )
        case Status.WAITING_FOR_ADDRESS_FLAT:
            insert_user_info(update.message.chat_id,
                             status=Status.WAITING_FOR_PHONE,
                             flat=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер телефона:</b>'
            )
        case Status.WAITING_FOR_PHONE:
            insert_user_info(update.message.chat_id,
                             status=Status.READY_NO_COMMENT,
                             phone=update.message.text)
            await update.message.reply_html(
                '<b>Хотите добавить комментарий?</b>',
                reply_markup=ReplyKeyboardMarkup(
                    [['Редактировать комментарий', 'Детали заказа']],
                    one_time_keyboard=True
                )
            )
        case Status.EDIT_COMMENT:
            insert_user_info(update.message.chat_id,
                             status=Status.READY,
                             comment=update.message.text)
            await check_details(update, context)
        case Status.EDIT_NAME:
            insert_user_info(update.message.chat_id, status=Status.READY,
                             name=update.message.text)
            await check_details(update, context)
        case Status.EDIT_ADDRESS_HOUSE:
            insert_user_info(update.message.chat_id,
                             status=Status.EDIT_ADDRESS_ENTRANCE,
                             house=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер подъезда:</b>'
            )
        case Status.EDIT_ADDRESS_ENTRANCE:
            insert_user_info(update.message.chat_id,
                             status=Status.EDIT_ADDRESS_FLOOR,
                             entrance=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер этажа:</b>'
            )
        case Status.EDIT_ADDRESS_FLOOR:
            insert_user_info(update.message.chat_id,
                             status=Status.EDIT_ADDRESS_FLAT,
                             floor=update.message.text)
            await update.message.reply_html(
                '<b>Введите номер квартиры:</b>'
            )
        case Status.EDIT_ADDRESS_FLAT:
            insert_user_info(update.message.chat_id, status=Status.READY,
                             flat=update.message.text)
            await check_details(update, context)
        case Status.EDIT_PHONE:
            insert_user_info(update.message.chat_id, status=Status.READY,
                             phone=update.message.text)
            await check_details(update, context)
        case _:
            await unknown(update, context)


async def edit_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    insert_user_info(update.message.chat_id, status=Status.EDIT_COMMENT)
    await update.message.reply_html(
        '<b>Введите комментарий:</b>'
    )


async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = get_user_details(update.message.chat_id)
    await context.bot.send_message(chat_id=413504212,
                                   text='<b>Детали заказа:</b>\n\n'
                                        '<b><i>Имя:</i></b>\n'
                                        f'{user_info[0]}\n'
                                        '<b><i>Адрес:</i></b>\n'
                                        f'{user_info[1]}\n'
                                        '<b><i>Номер телефона:</i></b>\n'
                                        f'{user_info[2]}\n'
                                        '<b><i>Комментарий:</i></b>\n'
                                        f'{user_info[3]}',
                                   parse_mode='HTML')
    await update.message.reply_html(
        '<b>Детали заказа:</b>\n\n'
        '<b><i>Имя:</i></b>\n'
        f'{user_info[0]}\n'
        '<b><i>Адрес:</i></b>\n'
        f'{user_info[1]}\n'
        '<b><i>Номер телефона:</i></b>\n'
        f'{user_info[2]}\n'
        '<b><i>Комментарий:</i></b>\n'
        f'{user_info[3]}\n\n'
        'В ближайшее время с вами свяжется наш сотрудник.\n'
        'Спасибо, что выбрали нас!',
        reply_markup=ReplyKeyboardMarkup(
            [['Вынести мусор']], one_time_keyboard=True
        )
    )


async def edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    insert_user_info(update.message.chat_id, status=Status.EDIT_NAME)
    await update.message.reply_html(
        '<b>Введите Имя:</b>'
    )


async def edit_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    insert_user_info(update.message.chat_id, status=Status.EDIT_ADDRESS_HOUSE)
    await update.message.reply_html(
        '<b>Введите номер дома:</b>'
    )


async def edit_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # pylint: disable=unused-argument
    insert_user_info(update.message.chat_id, status=Status.EDIT_PHONE)
    await update.message.reply_html(
        '<b>Введите номер телефона:</b>'
    )


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text='Сорри, я не знаю таких команд.')


conn = None


def get_user_details(chat_id):
    cur = conn.cursor()
    cur.execute(
        f'SELECT name, house, entrance, floor, flat, phone, comment, status '
        f'FROM user_info WHERE chat_id = {chat_id};')

    return cur.fetchone()


def get_user_status(chat_id):
    cur = conn.cursor()
    cur.execute(f'SELECT status '
                f'FROM user_info WHERE chat_id = {chat_id};')

    return cur.fetchone()


def user_info_filled(chat_id):
    cur = conn.cursor()
    cur.execute(f'SELECT info_filled '
                f'FROM user_info WHERE chat_id = {chat_id};')

    return cur.fetchone()


def insert_user_info(chat_id, status=Status.STARTED, **kwargs):
    sql = ''
    if status == Status.STARTED:
        user_status = get_user_status(chat_id)
        if user_status is None:
            sql = (f'INSERT OR IGNORE INTO user_info(chat_id, status) '
                   f'VALUES ({chat_id}, {status});')
        else:
            sql = (f'UPDATE user_info '
                   f'SET status = {status} '
                   f'WHERE chat_id = {chat_id};')
    else:
        user_status = get_user_status(chat_id)[0]
        match user_status:
            case Status.STARTED | Status.READY | Status.READY_NO_COMMENT:
                sql = (f'UPDATE user_info '
                       f'SET status = {status} '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_NAME:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, name = "{kwargs["name"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_ADDRESS_HOUSE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, house = "{kwargs["house"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_ADDRESS_ENTRANCE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, '
                       f'entrance = "{kwargs["entrance"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_ADDRESS_FLOOR:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, floor = "{kwargs["floor"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_ADDRESS_FLAT:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, flat = "{kwargs["flat"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.WAITING_FOR_PHONE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, '
                       f'phone = "{kwargs["phone"]}", '
                       f'info_filled = 1 '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_COMMENT:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, '
                       f'comment = "{kwargs["comment"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_NAME:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, name = "{kwargs["name"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_PHONE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, phone = "{kwargs["phone"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_ADDRESS_HOUSE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, house = "{kwargs["house"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_ADDRESS_ENTRANCE:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, '
                       f'entrance = "{kwargs["entrance"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_ADDRESS_FLOOR:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, floor = "{kwargs["floor"]}" '
                       f'WHERE chat_id = {chat_id};')
            case Status.EDIT_ADDRESS_FLAT:
                sql = (f'UPDATE user_info '
                       f'SET status = {status}, flat = "{kwargs["flat"]}" '
                       f'WHERE chat_id = {chat_id};')

    cur = conn.cursor()
    try:
        cur.execute(sql)
    except sqlite3.ProgrammingError:
        pass
    conn.commit()


if __name__ == '__main__':
    database = r'D:\учеба\прога\PyCharm\TrashBot\trashbotDB.db'

    sql_create_user_info_table = ('CREATE TABLE IF NOT EXISTS user_info ('
                                  'id INTEGER PRIMARY KEY, '
                                  'chat_id INTEGER NOT NULL UNIQUE, '
                                  'name TEXT, '
                                  'house TEXT, '
                                  'entrance TEXT, '
                                  'floor TEXT, '
                                  'flat TEXT, '
                                  'phone TEXT, '
                                  'comment TEXT, '
                                  'status INTEGER NOT NULL, '
                                  'info_filled INTEGER NOT NULL DEFAULT 0);')

    # create a database connection
    conn = create_connection(database)

    # create tables
    if conn is not None:
        # create projects table
        create_table(conn, sql_create_user_info_table)
    else:
        print('Error! cannot create the database connection.')

    application = ApplicationBuilder().token(TOKEN).build()

    start_handler = CommandHandler('start', start)
    check_details_handler = MessageHandler(
        filters.Text(['Вынести мусор']) | filters.Text(['Детали заказа']),
        check_details)
    text_handler = MessageHandler(
        filters.TEXT & ~ filters.Text(['Вынести мусор',
                                       'Редактировать комментарий',
                                       'Оформить заказ',
                                       'Детали заказа',
                                       'Редактировать имя',
                                       'Редактировать адрес',
                                       'Редактировать номер']),
        process_text)
    add_comment_handler = MessageHandler(
        filters.Text(['Редактировать комментарий']),
        edit_comment)
    place_order_handler = MessageHandler(
        filters.Text(['Оформить заказ']),
        place_order)
    edit_name_handler = MessageHandler(
        filters.Text(['Редактировать имя']),
        edit_name)
    edit_address_handler = MessageHandler(
        filters.Text(['Редактировать адрес']),
        edit_address)
    edit_phone_handler = MessageHandler(
        filters.Text(['Редактировать номер']),
        edit_phone)

    application.add_handler(start_handler)
    application.add_handler(check_details_handler)
    application.add_handler(text_handler)
    application.add_handler(add_comment_handler)
    application.add_handler(place_order_handler)

    # Other handlers
    unknown_handler = MessageHandler(filters.COMMAND, unknown)
    application.add_handler(unknown_handler)

    application.run_polling()
