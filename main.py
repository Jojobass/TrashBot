"""imports: telegram & telegram.ext are from python-telegram-bot"""
import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, \
    CommandHandler, ContextTypes

TOKEN = '5025597859:AAEWXRIIXFHWLeC7kCZThTzokzZigK2d2Uc'
OWNER_CHAT = 413504212

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
     READY, SELECT_SERVICE, WAITING_FOR_PAYMENT) = range(18)


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
                                      'name TEXT, '
                                      'house TEXT, '
                                      'entrance TEXT, '
                                      'floor TEXT, '
                                      'flat TEXT, '
                                      'phone TEXT, '
                                      'comment TEXT, '
                                      'last_order TEXT, '
                                      'status INTEGER NOT NULL, '
                                      'info_filled INTEGER NOT NULL DEFAULT 0'
                                      ');')

        # create a database connection
        self.conn = self.create_connection(database)

        # create tables
        if self.conn is not None:
            # create projects table
            self.create_table(self.conn, sql_create_user_info_table)
        else:
            print('Error! cannot create the database connection.')

    def build_app(self):
        self.application = ApplicationBuilder().token(TOKEN).build()

        start_handler = CommandHandler('start', self.start)
        check_details_handler = MessageHandler(
            filters.Text(['Вынести мусор', 'Детали заказа']),
            self.check_details)
        text_handler = MessageHandler(
            filters.TEXT & ~filters.Text(['Вынести мусор',
                                          'Редактировать комментарий',
                                          'Оформить заказ',
                                          'Детали заказа',
                                          'Редактировать имя',
                                          'Редактировать адрес',
                                          'Редактировать номер',
                                          'Выбрать услугу',
                                          '1 Пакет +1 бутылка [100₽]',
                                          '2 Пакета +2 бутылки [150₽]',
                                          '3-5 пакетов +3 бутылки [225₽]']),
            self.process_text)
        add_comment_handler = MessageHandler(
            filters.Text(['Редактировать комментарий']),
            self.edit_comment)
        place_order_handler = MessageHandler(
            filters.Text(['Оформить заказ']),
            self.place_order)
        edit_name_handler = MessageHandler(
            filters.Text(['Редактировать имя']),
            self.edit_name)
        edit_address_handler = MessageHandler(
            filters.Text(['Редактировать адрес']),
            self.edit_address)
        edit_phone_handler = MessageHandler(
            filters.Text(['Редактировать номер']),
            self.edit_phone)
        select_service_handler = MessageHandler(
            filters.Text(['Выбрать услугу']),
            self.select_service)
        process_payment_handler = MessageHandler(
            filters.Text(['1 Пакет +1 бутылка [100₽]',
                          '2 Пакета +2 бутылки [150₽]',
                          '3-5 пакетов +3 бутылки [225₽]']),
            self.process_payment)

        self.application.add_handler(start_handler)
        self.application.add_handler(check_details_handler)
        self.application.add_handler(text_handler)
        self.application.add_handler(add_comment_handler)
        self.application.add_handler(place_order_handler)
        self.application.add_handler(edit_name_handler)
        self.application.add_handler(edit_address_handler)
        self.application.add_handler(edit_phone_handler)
        self.application.add_handler(select_service_handler)
        self.application.add_handler(process_payment_handler)

        # Other handlers
        unknown_handler = MessageHandler(filters.COMMAND, self.unknown)
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

    def get_user_details(self, chat_id):
        """Get all user details from DB.

        :return: list([str, ...])
        """
        cur = self.conn.cursor()
        cur.execute(
            f'SELECT name, '
            f'house, '
            f'entrance, '
            f'floor, '
            f'flat, '
            f'phone, '
            f'comment '
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

    def insert_user_info(self, chat_id, status=Status.STARTED, **kwargs):
        """Updates DB based on user status in DB.

        If it's a first-time user inserts into DB.
        If DB status is STARTED, READY or READY_NO_COMMENT only updates status.
        Else updates corresponding value and status.
        """
        sql = ''
        if status == Status.STARTED:
            user_status = self.get_user_status(chat_id)
            if user_status is None:
                sql = (f'INSERT OR IGNORE INTO user_info(chat_id, status) '
                       f'VALUES ({chat_id}, {status});')
            else:
                sql = (f'UPDATE user_info '
                       f'SET status = {status} '
                       f'WHERE chat_id = {chat_id};')
        else:
            user_status = self.get_user_status(chat_id)[0]
            match user_status:
                case (Status.STARTED | Status.READY |
                      Status.READY_NO_COMMENT | Status.SELECT_SERVICE):
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

        cur = self.conn.cursor()
        try:
            cur.execute(sql)
        except sqlite3.ProgrammingError:
            pass
        self.conn.commit()
        cur.close()

    # ----------------- Handler for custom input info--------------------------

    async def process_text(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """Performs operations based on user status in DB.

        Status is formulated like 'waiting for ...' or 'edit ...',
        which means we need to update corresponding value in DB & status.
        """
        user_status = self.get_user_status(update.message.chat_id)[0]
        match user_status:
            case Status.WAITING_FOR_NAME:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.WAITING_FOR_ADDRESS_HOUSE,
                                      name=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер дома:</b>'
                )
            case Status.WAITING_FOR_ADDRESS_HOUSE:
                self.insert_user_info(
                    update.message.chat_id,
                    status=Status.WAITING_FOR_ADDRESS_ENTRANCE,
                    house=update.message.text
                )
                await update.message.reply_html(
                    '<b>Введите номер подъезда:</b>'
                )
            case Status.WAITING_FOR_ADDRESS_ENTRANCE:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.WAITING_FOR_ADDRESS_FLOOR,
                                      entrance=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер этажа:</b>'
                )
            case Status.WAITING_FOR_ADDRESS_FLOOR:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.WAITING_FOR_ADDRESS_FLAT,
                                      floor=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер квартиры:</b>'
                )
            case Status.WAITING_FOR_ADDRESS_FLAT:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.WAITING_FOR_PHONE,
                                      flat=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер телефона:</b>'
                )
            case Status.WAITING_FOR_PHONE:
                self.insert_user_info(update.message.chat_id,
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
                await update.message.reply_html(
                    '<b>Введите номер подъезда:</b>'
                )
            case Status.EDIT_ADDRESS_ENTRANCE:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.EDIT_ADDRESS_FLOOR,
                                      entrance=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер этажа:</b>'
                )
            case Status.EDIT_ADDRESS_FLOOR:
                self.insert_user_info(update.message.chat_id,
                                      status=Status.EDIT_ADDRESS_FLAT,
                                      floor=update.message.text)
                await update.message.reply_html(
                    '<b>Введите номер квартиры:</b>'
                )
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
        self.insert_user_info(update.message.chat_id)

        reply_keyboard = [['Вынести мусор']]

        await update.message.reply_html(
            'Привет!👋\n'
            'Я - бот, который поможет тебе вынести 🗑!\n'
            'Нажми на кнопку [Вынести мусор]',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True
            )
        )

    async def check_details(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        """Check user details if filled.

        Column info_filled is set to 1 after first filling the user details.
        So if it's 0, gotta fill the details.
        Else, show all details to user, who can edit them or order.
        """
        user_info = self.get_user_details(update.message.chat_id)
        user_filled = self.user_info_filled(update.message.chat_id)[0]
        if not user_filled:
            self.insert_user_info(update.message.chat_id,
                                  status=Status.WAITING_FOR_NAME)
            await update.message.reply_html(
                '<b>Введите Имя:</b>'
            )
        else:
            await update.message.reply_html(
                '<b>Сохраненные данные:</b>\n\n'
                '<b><i>Имя:</i></b>\n'
                f'{user_info[0]}\n'
                '<b><i>Адрес:</i></b>\n'
                f'{user_info[1]}, {user_info[2]}, '
                f'{user_info[3]}, {user_info[4]}\n'
                '<b><i>Номер телефона:</i></b>\n'
                f'{user_info[5]}\n'
                '<b><i>Комментарий:</i></b>\n'
                f'{user_info[6]}',
                reply_markup=ReplyKeyboardMarkup(
                    [['Редактировать имя', 'Редактировать адрес'],
                     ['Редактировать номер', 'Редактировать комментарий'],
                     ['Выбрать услугу']],
                    one_time_keyboard=True
                )
            )

    async def edit_comment(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id,
                              status=Status.EDIT_COMMENT)
        await update.message.reply_html(
            '<b>Введите комментарий:</b>'
        )

    async def edit_name(self, update: Update,
                        context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id, status=Status.EDIT_NAME)
        await update.message.reply_html(
            '<b>Введите Имя:</b>'
        )

    async def edit_address(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id,
                              status=Status.EDIT_ADDRESS_HOUSE)
        await update.message.reply_html(
            '<b>Введите номер дома:</b>'
        )

    async def edit_phone(self, update: Update,
                         context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id, status=Status.EDIT_PHONE)
        await update.message.reply_html(
            '<b>Введите номер телефона:</b>'
        )

    async def select_service(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        self.insert_user_info(update.message.chat_id,
                              status=Status.SELECT_SERVICE)
        await update.message.reply_html(
            '<b>Выберите услугу:</b>',
            reply_markup=ReplyKeyboardMarkup(
                [['1 Пакет +1 бутылка [100₽]'],
                 ['2 Пакета +2 бутылки [150₽]'],
                 ['3-5 пакетов +3 бутылки [225₽]'],
                 ['Назад']], one_time_keyboard=True
            )
        )

    async def process_payment(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        # pylint: disable=unused-argument
        await update.message.reply_html(
            'ЗДЕСЬ БУДЕТ ОПЛАТА',
            reply_markup=ReplyKeyboardMarkup(
                [['Оформить заказ']], one_time_keyboard=True
            )
        )

    async def place_order(self, update: Update,
                          context: ContextTypes.DEFAULT_TYPE):
        """Send order to owner chat, show order details to user."""
        self.insert_user_info(update.message.chat_id, status=Status.READY)
        user_info = self.get_user_details(update.message.chat_id)
        await context.bot.send_message(chat_id=OWNER_CHAT,
                                       text='<b>Детали заказа:</b>\n\n'
                                            '<b><i>Имя:</i></b>\n'
                                            f'{user_info[0]}\n'
                                            '<b><i>Адрес:</i></b>\n'
                                            f'д.{user_info[1]}, '
                                            f'под.{user_info[2]}, '
                                            f'эт.{user_info[3]}, '
                                            f'кв.{user_info[4]}\n'
                                            '<b><i>Номер телефона:</i></b>\n'
                                            f'{user_info[5]}\n'
                                            '<b><i>Комментарий:</i></b>\n'
                                            f'{user_info[6]}',
                                       parse_mode='HTML')
        await update.message.reply_html(
            '<b>Детали заказа:</b>\n\n'
            '<b><i>Имя:</i></b>\n'
            f'{user_info[0]}\n'
            '<b><i>Адрес:</i></b>\n'
            f'д.{user_info[1]}, под.{user_info[2]}, '
            f'эт.{user_info[3]}, кв.{user_info[4]}\n'
            '<b><i>Номер телефона:</i></b>\n'
            f'{user_info[5]}\n'
            '<b><i>Комментарий:</i></b>\n'
            f'{user_info[6]}\n\n'
            'В ближайшее время с вами свяжется наш сотрудник.\n'
            'Спасибо, что выбрали нас!',
            reply_markup=ReplyKeyboardMarkup(
                [['Вынести мусор']], one_time_keyboard=True
            )
        )


    @staticmethod
    async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text='Сорри, я не знаю таких команд.')


if __name__ == '__main__':
    bot = TrashBot()
    bot.run()
