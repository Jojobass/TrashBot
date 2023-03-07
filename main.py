"""imports: telegram & telegram.ext are from python-telegram-bot"""
import logging
import sqlite3
import re
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    error
)
from telegram.ext import (
    filters,
    MessageHandler,
    CallbackQueryHandler,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

TOKEN = '5025597859:AAEWXRIIXFHWLeC7kCZThTzokzZigK2d2Uc'
OWNER_CHAT = -801906112
OWNER_USERNAME = '@Jojobasc'
OWNER_CARD = '#### #### #### ####'
OWNER_NAME = 'Иванов Иван Иванович'
BOT_NAME = '@Malakhov_BKIT_bot'

HOUSE_BUTTONS = [['2', '20А']]
ENTRANCE_BUTTONS = [['А', 'Б', 'В', 'Г'],
                    ['Д', 'Е', 'Ж', 'И']]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


class Status:
    (STARTED, WAITING_FOR_NAME, WAITING_FOR_ADDRESS_HOUSE,
     WAITING_FOR_ADDRESS_ENTRANCE, WAITING_FOR_ADDRESS_FLOOR,
     WAITING_FOR_ADDRESS_FLAT, WAITING_FOR_PHONE,
     EDIT_NAME, EDIT_ADDRESS_HOUSE, EDIT_ADDRESS_ENTRANCE,
     EDIT_ADDRESS_FLOOR, EDIT_ADDRESS_FLAT, EDIT_PHONE, EDIT_COMMENT,
     READY, SELECT_SERVICE, WAITING_FOR_PAYMENT) = range(17)


class OrderStatus:
    PROCESSING = 'Заказ обрабатывается'
    ACCEPTED = 'Курьер принял ваш заказ'
    EN_ROUTE = 'Курьер в пути'
    DONE = 'Заказ выполнен'
    REJECTED = 'Отменен'


class TrashBot:
    """Telegram bot application & DB handler"""

    def __init__(self):
        self.application = None
        self.conn = None
        self.connect()
        self.build_app()

    def __del__(self):
        self.conn.close()

    def connect(self):
        database = r'trashbotDB.db'

        sql_create_user_info_table = ('CREATE TABLE IF NOT EXISTS user_info ('
                                      'id INTEGER PRIMARY KEY, '
                                      'chat_id INTEGER NOT NULL UNIQUE, '
                                      'username TEXT NOT NULL UNIQUE, '
                                      'name TEXT, '
                                      'house TEXT, '
                                      'entrance TEXT, '
                                      'floor TEXT, '
                                      'flat TEXT, '
                                      'phone TEXT, '
                                      'comment TEXT, '
                                      'cur_service TEXT, '
                                      'status INTEGER NOT NULL, '
                                      'info_filled INTEGER NOT NULL DEFAULT 0'
                                      ');')
        sql_create_order_info_table = ('CREATE TABLE IF NOT EXISTS order_info ('
                                       'id INTEGER PRIMARY KEY, '
                                       'customer_id INTEGER NOT NULL, '
                                       'customer_username TEXT, '
                                       'name TEXT, '
                                       'address TEXT, '
                                       'phone TEXT, '
                                       'comment TEXT, '
                                       'service TEXT, '
                                       'worker_username TEXT, '
                                       'status TEXT '
                                       f'default "{OrderStatus.PROCESSING}", '
                                       'order_datetime INTEGER);')

        # create a database connection
        self.conn = self.create_connection(database)

        # create tables
        if self.conn is not None:
            # create projects table
            self.create_table(self.conn, sql_create_user_info_table)
            self.create_table(self.conn, sql_create_order_info_table)
        else:
            print('Error! cannot create the database connection.')

    ALL_KEYWORDS = ['Вынести мусор',
                    'Редактировать комментарий',
                    'Добавить комментарий',
                    'Детали заказа',
                    'Редактировать имя',
                    'Редактировать адрес',
                    'Редактировать номер',
                    'Выбрать услугу',
                    '1 Пакет +1 бутылка [100₽]',
                    '2 Пакета +2 бутылки [150₽]',
                    '3-5 пакетов +3 бутылки [225₽]',
                    'Назад',
                    'Поддержка']

    def build_app(self):
        self.application = (ApplicationBuilder()
                            .token(TOKEN)
                            .get_updates_http_version('1.1')
                            .http_version('1.1')
                            .build())
        start_handler = CommandHandler('start', self.start,
                                       filters=filters.ChatType.PRIVATE)
        show_support_handler = MessageHandler(
            filters.ChatType.PRIVATE & filters.Text(['Поддержка']),
            self.show_support)
        check_details_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Вынести мусор', 'Детали заказа', 'Назад']),
            self.check_details)
        text_handler = MessageHandler(
            (filters.TEXT &
             filters.ChatType.PRIVATE &
             ~filters.Text(self.ALL_KEYWORDS)),
            self.process_text)
        add_comment_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Редактировать комментарий', 'Добавить комментарий']),
            self.edit_comment)
        edit_name_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Редактировать имя']),
            self.edit_name)
        edit_address_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Редактировать адрес']),
            self.edit_address)
        edit_phone_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Редактировать номер']),
            self.edit_phone)
        select_service_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['Выбрать услугу']),
            self.select_service)
        request_payment_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            filters.Text(['1 Пакет +1 бутылка [100₽]',
                          '2 Пакета +2 бутылки [150₽]',
                          '3-5 пакетов +3 бутылки [225₽]']),
            self.request_payment)
        place_order_handler = MessageHandler(
            filters.ChatType.PRIVATE &
            (filters.PHOTO | filters.Document.IMAGE | filters.Document.PDF),
            self.place_order)

        # pylint: disable=consider-using-f-string
        assign_order_handler = MessageHandler(
            (filters.Regex(re.compile('^{BOT_NAME} [0-9]+ @[A-Za-z0-9_]+'
                                      .format(BOT_NAME=BOT_NAME))) &
             filters.Chat(chat_id=OWNER_CHAT, allow_empty=True) &
             filters.User(username=OWNER_USERNAME, allow_empty=True)),
            self.assign_order)
        update_order_status_handler = CallbackQueryHandler(
            self.update_order_status,
            pattern=f'[0-9]+ ({OrderStatus.EN_ROUTE})|'
                    f'[0-9]+ ({OrderStatus.DONE})'
        )
        incorrect_order_handler = MessageHandler(
            (filters.Regex(re.compile('^{BOT_NAME} [0-9]+ incorrect'
                                      .format(BOT_NAME=BOT_NAME))) &
             filters.Chat(chat_id=OWNER_CHAT, allow_empty=True) &
             filters.User(username=OWNER_USERNAME, allow_empty=True)),
            self.incorrect_order)
        reject_order_handler = MessageHandler(
            (filters.Regex(re.compile('^{BOT_NAME} [0-9]+ reject'
                                      .format(BOT_NAME=BOT_NAME))) &
             filters.Chat(chat_id=OWNER_CHAT, allow_empty=True) &
             filters.User(username=OWNER_USERNAME, allow_empty=True)),
            self.reject_order)

        self.application.add_handler(show_support_handler)
        self.application.add_handler(start_handler)
        self.application.add_handler(check_details_handler)
        self.application.add_handler(text_handler)
        self.application.add_handler(add_comment_handler)
        self.application.add_handler(place_order_handler)
        self.application.add_handler(edit_name_handler)
        self.application.add_handler(edit_address_handler)
        self.application.add_handler(edit_phone_handler)
        self.application.add_handler(select_service_handler)
        self.application.add_handler(request_payment_handler)
        self.application.add_handler(assign_order_handler)
        self.application.add_handler(update_order_status_handler)
        self.application.add_handler(incorrect_order_handler)
        self.application.add_handler(reject_order_handler)

        # Other handlers
        unknown_handler = MessageHandler(filters.ChatType.PRIVATE &
                                         filters.COMMAND,
                                         self.unknown)
        self.application.add_handler(unknown_handler)

    def run(self):
        self.application.run_polling()

    # ---------------------------- DB methods ---------------------------------

    @staticmethod
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

    @staticmethod
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

    # --------- user_info methods ---------------

    def get_user_details(self, chat_id):
        """Get all user details from DB.

        :return: list([str(name),
        str(house),
        str(entrance),
        str(floor),
        str(flat),
        str(phone),
        str(comment),
        str(cur_service)])
        """
        cur = self.conn.cursor()
        cur.execute(
            f'SELECT name, '
            f'house, '
            f'entrance, '
            f'floor, '
            f'flat, '
            f'phone, '
            f'comment, '
            f'cur_service '
            f'FROM user_info WHERE chat_id = {chat_id};')

        return cur.fetchone()

    def get_user_status(self, chat_id):
        """Get user status from DB.

        :return: list([int(status)])
        """
        cur = self.conn.cursor()
        cur.execute(f'SELECT status '
                    f'FROM user_info WHERE chat_id = {chat_id};')

        return cur.fetchone()

    def user_info_filled(self, chat_id):
        """Get info_filled from DB.

        :return: list([int(info_filled)])
        """
        cur = self.conn.cursor()
        cur.execute(f'SELECT info_filled '
                    f'FROM user_info WHERE chat_id = {chat_id};')

        return cur.fetchone()

    def get_user_by_username(self, username):
        cur = self.conn.cursor()
        cur.execute(f'SELECT chat_id '
                    f'FROM user_info WHERE username = "{username[1:]}";')

        return cur.fetchone()

    def insert_user_info(self, chat_id, status=Status.STARTED, **kwargs):
        """Updates DB based on user status in DB.

        If it's a first-time user inserts into DB.
        If DB status is STARTED, READY only updates status.
        Else updates corresponding value and status.
        """
        sql = ''
        if status == Status.STARTED:
            user_status = self.get_user_status(chat_id)
            if user_status is None:
                sql = (f'INSERT OR IGNORE '
                       f'INTO user_info(chat_id, status, username) '
                       f'VALUES ({chat_id}, '
                       f'{status}, '
                       f'"{kwargs["username"]}"'
                       f');')
            else:
                sql = (f'UPDATE user_info '
                       f'SET status = {status} '
                       f'WHERE chat_id = {chat_id};')
        elif status == Status.READY and len(kwargs) == 0:
            sql = (f'UPDATE user_info '
                   f'SET status = {status} '
                   f'WHERE chat_id = {chat_id};')
        else:
            user_status = self.get_user_status(chat_id)[0]
            match user_status:
                case Status.READY:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status} '
                           f'WHERE chat_id = {chat_id};')
                case Status.WAITING_FOR_NAME:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'name = "{kwargs["name"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.WAITING_FOR_ADDRESS_HOUSE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'house = "{kwargs["house"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.WAITING_FOR_ADDRESS_ENTRANCE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'entrance = "{kwargs["entrance"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.WAITING_FOR_ADDRESS_FLOOR:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'floor = "{kwargs["floor"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.WAITING_FOR_ADDRESS_FLAT:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'flat = "{kwargs["flat"]}" '
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
                           f'SET status = {status}, '
                           f'name = "{kwargs["name"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.EDIT_PHONE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'phone = "{kwargs["phone"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.EDIT_ADDRESS_HOUSE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'house = "{kwargs["house"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.EDIT_ADDRESS_ENTRANCE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'entrance = "{kwargs["entrance"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.EDIT_ADDRESS_FLOOR:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'floor = "{kwargs["floor"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.EDIT_ADDRESS_FLAT:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'flat = "{kwargs["flat"]}" '
                           f'WHERE chat_id = {chat_id};')
                case Status.SELECT_SERVICE:
                    sql = (f'UPDATE user_info '
                           f'SET status = {status}, '
                           f'cur_service = "{kwargs["cur_service"]}" '
                           f'WHERE chat_id = {chat_id};')

        cur = self.conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.ProgrammingError:
            pass
        self.conn.commit()
        cur.close()

    # --------- order_info methods ---------------

    def get_order_id(self, chat_id):
        sql = (f'SELECT id FROM order_info WHERE customer_id = {chat_id} '
               f'ORDER BY id DESC LIMIT 1;')
        cur = self.conn.cursor()
        cur.execute(sql)

        return cur.fetchone()

    def check_order_pending(self, order_id):
        sql = f'SELECT status FROM order_info WHERE id = {order_id};'
        cur = self.conn.cursor()
        cur.execute(sql)

        status = cur.fetchone()
        return (status is not None) and (status[0] == OrderStatus.PROCESSING)

    def get_customer_id(self, order_id):
        sql = f'SELECT customer_id FROM order_info WHERE id = {order_id};'
        cur = self.conn.cursor()
        cur.execute(sql)

        return cur.fetchone()

    def get_order_info(self, order_id):
        """Get all user details from DB.

        :return:
        list([int(order_id),
        int(customer_id),
        str(customer_username),
        str(name),
        str(address),
        str(phone),
        str(comment),
        str(service),
        str(worker_username),
        str(status),
        str(order_datetime)])
        """
        sql = ('SELECT '
               'id, '
               'customer_id, '
               'customer_username, '
               'name, '
               'address, '
               'phone, '
               'comment, '
               'service, '
               'worker_username, '
               'status, '
               'datetime(order_datetime, "unixepoch", "+3 hours") '
               f'FROM order_info WHERE id = {order_id};')
        cur = self.conn.cursor()
        cur.execute(sql)

        return cur.fetchone()

    def insert_order_info(self, order_id=None,
                          status=None, **kwargs):
        sql = ''
        if order_id is None:
            sql = ('INSERT OR IGNORE '
                   'INTO '
                   'order_info('
                   'customer_id, '
                   'customer_username, '
                   'name, '
                   'address, '
                   'phone, '
                   'comment, '
                   'service,'
                   'order_datetime) '
                   f'VALUES ({kwargs["customer_id"]}, '
                   f'"{kwargs["customer_username"]}", '
                   f'"{kwargs["name"]}", '
                   f'"{kwargs["address"]}", '
                   f'"{kwargs["phone"]}", '
                   f'"{kwargs["comment"]}", '
                   f'"{kwargs["service"]}", '
                   '(strftime("%s","now"))'
                   ');')
        elif status == OrderStatus.ACCEPTED:
            sql = (f'UPDATE order_info '
                   f'SET status = "{status}", '
                   f'worker_username = "{kwargs["worker_username"]}" '
                   f'WHERE id = {order_id};')
        else:
            sql = (f'UPDATE order_info '
                   f'SET status = "{status}" '
                   f'WHERE id = {order_id};')

        cur = self.conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.ProgrammingError:
            pass
        self.conn.commit()
        cur.close()

    def reject_order_db(self, order_id):
        sql = ('UPDATE order_info '
               f'SET status = "{OrderStatus.REJECTED}" '
               f'WHERE id = {order_id};')
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.ProgrammingError:
            pass
        self.conn.commit()
        cur.close()

    # ----------------------- Messaging methods -------------------------------

    async def send_message(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE,
                           chat_id, text, parse_mode=None, reply_markup=None,
                           raise_=False):
        try:
            await context.bot.send_message(chat_id=chat_id,
                                           text=text,
                                           parse_mode=parse_mode,
                                           reply_markup=reply_markup)
        except error.TimedOut as e:
            await self.reply_html(update, context,
                                  'Истекло ожидание ответа от сервера Telegram.'
                                  '\nПожалуйста, попробуйте еще раз')
            if raise_:
                raise e
        except (error.BadRequest, error.Forbidden) as e:
            if raise_:
                raise e

    @staticmethod
    async def reply_html(update: Update,
                         context: ContextTypes.DEFAULT_TYPE,
                         text, reply_markup=None, raise_=False):
        # pylint: disable=unused-argument
        try:
            await update.message.reply_html(text, reply_markup=reply_markup)
        except error.TelegramError as e:
            if raise_:
                raise e

    @staticmethod
    async def reply_markdown(update: Update,
                             context: ContextTypes.DEFAULT_TYPE,
                             text, reply_markup=None, raise_=False):
        # pylint: disable=unused-argument
        try:
            await update.message.reply_markdown(text, reply_markup=reply_markup)
        except error.TelegramError as e:
            if raise_:
                raise e

    async def forward_message(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE,
                              chat_id, from_chat_id, message_id, raise_=False):
        try:
            await context.bot.forward_message(chat_id=chat_id,
                                              from_chat_id=from_chat_id,
                                              message_id=message_id)
        except error.TimedOut as e:
            await self.reply_html(update, context,
                                  'Истекло ожидание ответа от сервера Telegram.'
                                  '\nПожалуйста, попробуйте еще раз')
            if raise_:
                raise e
        except (error.BadRequest, error.Forbidden) as e:
            if raise_:
                raise e

    # -------------------- Handlers for workers -------------------------------

    async def send_order(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE,
                         order_info):
        # pylint: disable=unused-argument
        await self.send_message(update, context,
                                chat_id=OWNER_CHAT,
                                text=f'<b>Детали заказа '
                                     f'#{order_info[0]}:</b>\n\n'
                                     f'{order_info[7]}\n'
                                     '<b><i>Контакт:</i></b>\n'
                                     f'@{order_info[2]}\n'
                                     '<b><i>Имя:</i></b>\n'
                                     f'{order_info[3]}\n'
                                     '<b><i>Адрес:</i></b>\n'
                                     f'{order_info[4]}\n'
                                     '<b><i>Номер телефона:</i></b>\n'
                                     f'{order_info[5]}\n'
                                     '<b><i>Комментарий:</i></b>\n'
                                     f'{order_info[6]}\n'
                                     '<b><i>Дата/время заказа:</i></b>\n'
                                     f'{order_info[10]}',
                                parse_mode='HTML',
                                raise_=True)
        await self.forward_message(update, context,
                                   chat_id=OWNER_CHAT,
                                   from_chat_id=update.message.chat_id,
                                   message_id=update.message.message_id,
                                   raise_=True)

    async def assign_order(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        rematch = re.search(r'([0-9]+) (@[A-Za-z0-9_]+)', update.message.text)
        order_id = rematch.group(1)
        worker_username = rematch.group(2)
        if not self.check_order_pending(order_id):
            await self.reply_html(
                update, context,
                f'Заказ <i>#{order_id}</i> не найден, отменен, выполнен, '
                f'либо исполнитель уже был присвоен!'
            )
        else:
            try:
                await self.send_order_to_worker(update, context, order_id,
                                                worker_username)
            except error.TelegramError:
                return
            else:
                await self.reply_html(
                    update, context,
                    f'Для заказа <i>#{order_id}</i> присвоен исполнитель: '
                    f'{worker_username}',
                )

    async def send_order_to_worker(self, update: Update,
                                   context: ContextTypes.DEFAULT_TYPE,
                                   order_id, worker_username):
        order_info = self.get_order_info(order_id)
        worker_id = self.get_user_by_username(worker_username)
        if worker_id is None:
            await self.reply_html(
                update, context,
                f'Исполнитель {worker_username} не начал беседу с ботом!'
            )
            raise error.BadRequest
        inline_keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton('Уже в пути',
                                      callback_data=f'{order_id} '
                                                    f'{OrderStatus.EN_ROUTE}')]
            ]
        )
        try:
            await self.send_message(update, context,
                                    chat_id=worker_id[0],
                                    text=f'<b>Детали заказа '
                                         f'#{order_info[0]}:</b>\n\n'
                                         f'{order_info[7]}\n'
                                         '<b><i>Контакт:</i></b>\n'
                                         f'@{order_info[2]}\n'
                                         '<b><i>Имя:</i></b>\n'
                                         f'{order_info[3]}\n'
                                         '<b><i>Адрес:</i></b>\n'
                                         f'{order_info[4]}\n'
                                         '<b><i>Номер телефона:'
                                         '</i></b>\n'
                                         f'{order_info[5]}\n'
                                         '<b><i>Комментарий:</i></b>\n'
                                         f'{order_info[6]}\n'
                                         '<b><i>'
                                         'Дата/время заказа:'
                                         '</i></b>\n'
                                         f'{order_info[10]}',
                                    parse_mode='HTML',
                                    reply_markup=inline_keyboard,
                                    raise_=True
                                    )
        except (error.BadRequest, error.Forbidden) as e:
            await self.reply_html(
                update, context,
                f'Ошибка! Возможно, исполнитель {worker_username}'
                f' не начал беседу с ботом!'
            )
            raise e
        else:
            self.insert_order_info(order_id,
                                   status=OrderStatus.ACCEPTED,
                                   worker_username=worker_username)
            await self.send_message(update, context,
                                    chat_id=order_info[1],
                                    text=f'Статус заказа '
                                         f'<i>#{order_id}</i>:\n'
                                         f'<b>'
                                         f'{OrderStatus.ACCEPTED}'
                                         f'</b>',
                                    parse_mode='HTML')

    async def update_order_status(self, update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        rematch = re.search(r'([0-9]+) (.+)', query.data)
        order_id = rematch.group(1)
        new_status = rematch.group(2)
        self.insert_order_info(order_id, status=new_status)
        customer_id = self.get_customer_id(order_id)[0]
        await self.send_message(update, context,
                                chat_id=customer_id,
                                text=f'Статус заказа '
                                     f'<i>#{order_id}</i>:\n'
                                     f'<b>{new_status}</b>',
                                parse_mode='HTML')

        if new_status == OrderStatus.EN_ROUTE:
            inline_keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton('Выполнено',
                                          callback_data=f'{order_id} '
                                                        f'{OrderStatus.DONE}')]
                ]
            )
            await query.edit_message_reply_markup(reply_markup=inline_keyboard)
        elif new_status == OrderStatus.DONE:
            await query.edit_message_text(
                text=query.message.text + '\n\n✅Выполнено'
            )

    async def incorrect_order(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        rematch = re.search(r'([0-9]+) incorrect', update.message.text)
        order_id = rematch.group(1)
        customer_id = self.get_customer_id(order_id)[0]

        await self.send_message(update, context,
                                chat_id=customer_id,
                                text='Возникли трудности '
                                     'с обработкой заказа,\n'
                                     'в ближайшее время с вами '
                                     'свяжется наш сотрудник',
                                parse_mode='HTML')

    async def reject_order(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        rematch = re.search(r'([0-9]+) reject', update.message.text)
        order_id = rematch.group(1)
        customer_id = self.get_customer_id(order_id)[0]

        await self.send_message(update, context,
                                chat_id=customer_id,
                                text=f'Заказ <i>#{order_id}</i> '
                                     'не был оплачен и '
                                     '<b>не будет выполнен</b>.\n'
                                     'Не согласны? '
                                     'Пишите в поддержку',
                                parse_mode='HTML')
        self.reject_order_db(order_id)

    # ----------------- Handler for custom input info--------------------------

    async def process_text(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """Performs operations based on user status in DB.

        Status is formulated like 'waiting for ...' or 'edit ...',
        which means we need to update corresponding value in DB & status.
        """
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            user_status = cur_status[0]
            match user_status:
                case Status.WAITING_FOR_NAME:
                    self.insert_user_info(
                        update.message.chat_id,
                        status=Status.WAITING_FOR_ADDRESS_HOUSE,
                        name=update.message.text
                    )
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер дома:</b>',
                                              reply_markup=ReplyKeyboardMarkup(
                                                  HOUSE_BUTTONS,
                                                  one_time_keyboard=True),
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.WAITING_FOR_ADDRESS_HOUSE:
                    self.insert_user_info(
                        update.message.chat_id,
                        status=Status.WAITING_FOR_ADDRESS_ENTRANCE,
                        house=update.message.text
                    )
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер подъезда:</b>',
                                              reply_markup=ReplyKeyboardMarkup(
                                                  ENTRANCE_BUTTONS,
                                                  one_time_keyboard=True),
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.WAITING_FOR_ADDRESS_ENTRANCE:
                    self.insert_user_info(
                        update.message.chat_id,
                        status=Status.WAITING_FOR_ADDRESS_FLOOR,
                        entrance=update.message.text
                    )
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер этажа:</b>',
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.WAITING_FOR_ADDRESS_FLOOR:
                    self.insert_user_info(
                        update.message.chat_id,
                        status=Status.WAITING_FOR_ADDRESS_FLAT,
                        floor=update.message.text
                    )
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер квартиры:</b>',
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.WAITING_FOR_ADDRESS_FLAT:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.WAITING_FOR_PHONE,
                                          flat=update.message.text)
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер телефона:</b>',
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.WAITING_FOR_PHONE:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.READY,
                                          phone=update.message.text)
                    try:
                        await self.reply_html(
                            update, context,
                            '<b>Хотите добавить комментарий?</b>',
                            reply_markup=ReplyKeyboardMarkup(
                                [['Добавить комментарий', 'Детали заказа']],
                                one_time_keyboard=True
                            ),
                            raise_=True
                        )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.EDIT_COMMENT:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.READY,
                                          comment=update.message.text)
                    await self.check_details(update, context)
                case Status.EDIT_NAME:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.READY,
                                          name=update.message.text)
                    await self.check_details(update, context)
                case Status.EDIT_ADDRESS_HOUSE:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.EDIT_ADDRESS_ENTRANCE,
                                          house=update.message.text)
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер подъезда:</b>',
                                              reply_markup=ReplyKeyboardMarkup(
                                                  ENTRANCE_BUTTONS,
                                                  one_time_keyboard=True),
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.EDIT_ADDRESS_ENTRANCE:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.EDIT_ADDRESS_FLOOR,
                                          entrance=update.message.text)
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер этажа:</b>',
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.EDIT_ADDRESS_FLOOR:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.EDIT_ADDRESS_FLAT,
                                          floor=update.message.text)
                    try:
                        await self.reply_html(update, context,
                                              '<b>Введите номер квартиры:</b>',
                                              raise_=True
                                              )
                    except error.TelegramError:
                        await self.reply_html(update, context,
                                              'Произошла ошибка '
                                              'связи с сервером.\n'
                                              'Пожалуйста, попробуйте еще раз.'
                                              )
                        await self.reset(update, context)
                case Status.EDIT_ADDRESS_FLAT:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.READY,
                                          flat=update.message.text)
                    await self.check_details(update, context)
                case Status.EDIT_PHONE:
                    self.insert_user_info(update.message.chat_id,
                                          status=Status.READY,
                                          phone=update.message.text)
                    await self.check_details(update, context)
                case _:
                    await self.unknown(update, context)

    # --------------------------- Handlers ------------------------------------

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id,
                              username=update.message.chat.username)

        reply_keyboard = [['Вынести мусор']]

        try:
            await self.reply_html(update, context,
                                  'Привет!👋\n'
                                  'Я - бот, который поможет тебе вынести 🗑!\n'
                                  'Нажми на кнопку [Вынести мусор]',
                                  reply_markup=ReplyKeyboardMarkup(
                                      reply_keyboard, one_time_keyboard=True
                                  ),
                                  raise_=True
                                  )
        except error.TelegramError:
            await self.reply_html(update, context,
                                  'Произошла ошибка '
                                  'связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context)

    async def check_details(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        """Show user details if filled.

        Column info_filled is set to 1 after first filling the user details.
        So if it's 0, gotta fill the details.
        Else, show all details to user, who can edit them or order.
        """
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reset(update, context, cur_status is None)
        else:
            user_info = self.get_user_details(update.message.chat_id)
            user_filled = self.user_info_filled(update.message.chat_id)[0]
            if not user_filled:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.WAITING_FOR_NAME)
                try:
                    await self.reply_html(update, context,
                                          '<b>Введите Имя:</b>',
                                          raise_=True
                                          )
                except error.TelegramError:
                    await self.reply_html(update, context,
                                          'Произошла ошибка '
                                          'связи с сервером.\n'
                                          'Пожалуйста, попробуйте еще раз.'
                                          )
                    await self.reset(update, context)
            else:
                try:
                    await self.reply_html(update, context,
                                          '<b>Сохраненные данные:</b>\n\n'
                                          '<b><i>Имя:</i></b>\n'
                                          f'{user_info[0]}\n'
                                          '<b><i>Адрес:</i></b>\n'
                                          f'д. {user_info[1]}, '
                                          f'под. {user_info[2]}, '
                                          f'эт. {user_info[3]}, '
                                          f'кв. {user_info[4]}\n'
                                          '<b><i>Номер телефона:</i></b>\n'
                                          f'{user_info[5]}\n'
                                          '<b><i>Комментарий:</i></b>\n'
                                          f'{user_info[6]}',
                                          reply_markup=ReplyKeyboardMarkup(
                                              [['Редактировать имя',
                                                'Редактировать адрес'],
                                               ['Редактировать номер',
                                                'Редактировать комментарий'],
                                               ['Выбрать услугу'],
                                               ['Поддержка']]
                                          ),
                                          raise_=True
                                          )
                except error.TelegramError:
                    await self.reply_html(update, context,
                                          'Произошла ошибка '
                                          'связи с сервером.\n'
                                          'Пожалуйста, попробуйте еще раз.'
                                          )
                    await self.reset(update, context)

    async def show_support(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        try:
            await self.reply_html(update, context,
                                  f'По всем вопросам пишите {OWNER_USERNAME}',
                                  raise_=True
                                  )
        except error.TelegramError:
            await self.reply_html(update, context,
                                  'Произошла ошибка '
                                  'связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context)

    async def reset(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE, no_info=False):
        if no_info:
            self.insert_user_info(update.message.chat_id,
                                  username=update.message.chat.username)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.READY)
        await self.check_details(update, context)

    async def edit_comment(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.EDIT_COMMENT)
            try:
                await self.reply_html(update, context,
                                      '<b>Введите комментарий:</b>',
                                      raise_=True
                                      )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                await self.reset(update, context)

    async def edit_name(self, update: Update,
                        context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.EDIT_NAME)
            try:
                await self.reply_html(update, context,
                                      '<b>Введите Имя:</b>',
                                      raise_=True
                                      )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                await self.reset(update, context)

    async def edit_address(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.EDIT_ADDRESS_HOUSE)
            try:
                await self.reply_html(update, context,
                                      '<b>Введите номер дома:</b>',
                                      reply_markup=ReplyKeyboardMarkup(
                                          HOUSE_BUTTONS,
                                          one_time_keyboard=True),
                                      raise_=True
                                      )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                await self.reset(update, context)

    async def edit_phone(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.EDIT_PHONE)
            try:
                await self.reply_html(update, context,
                                      '<b>Введите номер телефона:</b>',
                                      raise_=True
                                      )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                await self.reset(update, context)

    async def select_service(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.READY:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.SELECT_SERVICE)
            try:
                await self.reply_html(update, context,
                                      '<b>Выберите услугу:</b>',
                                      reply_markup=ReplyKeyboardMarkup(
                                          [['1 Пакет +1 бутылка [100₽]'],
                                           ['2 Пакета +2 бутылки [150₽]'],
                                           ['3-5 пакетов +3 бутылки [225₽]'],
                                           ['Назад']], one_time_keyboard=True
                                      ),
                                      raise_=True
                                      )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                await self.reset(update, context)

    async def request_payment(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.SELECT_SERVICE:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.WAITING_FOR_PAYMENT,
                                  cur_service=update.message.text)
            user_info = self.get_user_details(update.message.chat_id)
            self.insert_order_info(customer_id=update.message.chat_id,
                                   customer_username=update.message
                                   .from_user.username,
                                   name=user_info[0],
                                   address=f'д. {user_info[1]}, '
                                           f'под. {user_info[2]}, '
                                           f'эт. {user_info[3]}, '
                                           f'кв. {user_info[4]}',
                                   phone=user_info[5],
                                   comment=user_info[6],
                                   service=user_info[7])
            order_id = self.get_order_id(update.message.chat_id)[0]
            try:
                await self.reply_markdown(
                    update, context,
                    'Для того, чтобы мы приняли ваш заказ, '
                    'переведите соответствующую сумму на\n'
                    f'`{OWNER_CARD}`\n'
                    f'({OWNER_NAME})\n'
                    f'с номером заказа `#{order_id}` в сообщении,\n'
                    'а затем **отправьте сюда скриншот платежа**',
                    reply_markup=ReplyKeyboardMarkup(
                        [['Назад']],
                        one_time_keyboard=True
                    ),
                    raise_=True
                )
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка '
                                      'связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
                self.reject_order_db(order_id)
                await self.reset(update, context)

    async def place_order(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
        """Insert order into order_info table,
        send order to owner chat, show order details to user."""

        cur_status = self.get_user_status(update.message.chat_id)
        if cur_status is None or cur_status[0] != Status.WAITING_FOR_PAYMENT:
            await self.reply_html(update, context,
                                  'Произошла ошибка связи с сервером.\n'
                                  'Пожалуйста, попробуйте еще раз.'
                                  )
            await self.reset(update, context, cur_status is None)
        else:
            self.insert_user_info(update.message.chat_id, status=Status.READY)
            order_id = self.get_order_id(update.message.chat_id)[0]
            order_info = self.get_order_info(order_id)
            try:
                await self.send_order(update, context, order_info)
            except error.TelegramError:
                await self.reply_html(update, context,
                                      'Произошла ошибка связи с сервером.\n'
                                      'Пожалуйста, попробуйте еще раз.'
                                      )
            else:
                await self.reply_html(
                    update, context,
                    f'<b>Детали заказа '
                    f'#{order_info[0]}:</b>\n\n'
                    f'{order_info[7]}\n'
                    '<b><i>Имя:</i></b>\n'
                    f'{order_info[3]}\n'
                    '<b><i>Адрес:</i></b>\n'
                    f'{order_info[4]}\n'
                    '<b><i>Номер телефона:</i></b>\n'
                    f'{order_info[5]}\n'
                    '<b><i>Комментарий:</i></b>\n'
                    f'{order_info[6]}\n'
                    '<b><i>Дата/время заказа:</i></b>\n'
                    f'{order_info[10]}\n\n'
                    'Заказ уже обрабатывается, '
                    'через несколько минут пришлем обновление статуса😉',
                    reply_markup=ReplyKeyboardMarkup(
                        [['Вынести мусор']],
                        one_time_keyboard=True
                    )
                )

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(update, context,
                                chat_id=update.effective_chat.id,
                                text='Сорри, я не знаю таких команд.')


if __name__ == '__main__':
    bot = TrashBot()
    bot.run()
