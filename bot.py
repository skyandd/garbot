#!/home/vladimir/anaconda3/bin/python
import misc
import telebot
import datetime
import os
import logging
import ssl

from telebot import types
from pyvirtualdisplay import Display
from telebot.types import Message
from classes import Car
from db_gta import add_telegram_public_user, get_user_cars, remove_car_from_check, add_car_for_check, add_start_user
from notifications import send_stats, upcoming_osago, car_sum_driver, department_sum, paid_and_new_fines, send_file, file_names, upcoming_service, get_users_dict
from aiohttp import web
from service_defs import WEBHOOK_PORT, WEBHOOK_LISTEN, WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV, WEBHOOK_URL_BASE, WEBHOOK_URL_PATH

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)
bot = telebot.TeleBot(misc.token)
app = web.Application()


# Process webhook calls
async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)


app.router.add_post('/{token}/', handle)


# ||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Bot logic

# --------------------------------------------------------------------------------------------------------------------
# Keyboards
def default_keyboard(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('/check - Проверить 🚗')
    if message.chat.id not in get_users_dict('telegram_users').keys():
        markup.row(types.KeyboardButton(text='/sign_up - Зарегистрироваться'))
    else:
        markup.row(types.KeyboardButton(text='/settings - Настройки'))

    if message.chat.id in get_users_dict('telegram_admin_users').values():
        markup.row('/get_stats - 🚗🚕🚙🚛🚘🚖🚍🚓🚕🚙🚗')
    markup.row('/help - Обратная связь')
    if message.chat.id == get_users_dict('telegram_admin_users')['Vladimir']:
        markup.row(types.KeyboardButton('bot_log'))
    return markup


def sign_up_keyboard(message, phone_number=None):
    keyboard = types.ReplyKeyboardMarkup()
    if phone_number is None:
        phone_btn = types.KeyboardButton('Продолжить регистрацию', request_contact=True)
        keyboard.add(phone_btn)
    if message.from_user.id in get_users_dict('telegram_users').keys():
        return default_keyboard(message)
    stop_reg = types.KeyboardButton('Прервать регистрацию')
    keyboard.add(stop_reg)

    return keyboard


def stats_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()

    btn_1 = types.InlineKeyboardButton(text='Штрафы', callback_data='btn_1')
    btn_2 = types.InlineKeyboardButton('ОСАГО', callback_data='btn_2')
    btn_3 = types.InlineKeyboardButton('Водители', callback_data='btn_3')
    btn_4 = types.InlineKeyboardButton('Отделы предприятия', callback_data='btn_4')
    btn_5 = types.InlineKeyboardButton('Оплаченные и новые штрафы', callback_data='btn_5')
    btn_6 = types.InlineKeyboardButton('Проверить автопарк', callback_data='btn_6')
    btn_7 = types.InlineKeyboardButton('Сервис/ТО', callback_data='btn_7')
    keyboard.row_width = 2
    keyboard.add(btn_1, btn_2, btn_3, btn_4, btn_7, btn_6, btn_5)
    return keyboard


def settings_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton('Добавить 🚗', callback_data='add_car_for_check'))
    keyboard.add(types.InlineKeyboardButton('Убрать 🚗 из проверки', callback_data='remove_car_from_check'))
    keyboard.row(types.InlineKeyboardButton('Список твоих авто', callback_data='show_user_car_list'))
    return keyboard


def remove_keyboard():
    keyboard = types.ReplyKeyboardRemove()
    return keyboard


# --------------------------------------------------------------------------------------------------------------------
# SERVICE DEFS
def process_car_check(message, sts=None):
    if sts is None:
        if message.text.lower() in ['нет', 'no', 'ytn', 'yt', 'не', 'yj']:
            bot.send_message(message.from_user.id, '༼ つ ◕_◕ ༽つ'
                                                   '\nНу нет, так нет'
                                                   '\nЧем ещё займёмся?', reply_markup=default_keyboard(message))
            return
        sts = message.text

    payment_keyboard = telebot.types.InlineKeyboardMarkup()
    payment_keyboard.row_width = 2
    car = Car('_', 607, '_', 607, 607)

    if len(str(sts)) == 10:
        car.sts = sts
        try:
            display = Display(visible=0, size=(320, 200))
            display.start()

            bot.send_message(message.from_user.id, f'Проверяю {sts}')
            bot.send_chat_action(message.from_user.id, 'typing')
            car.id = f'{message.chat.first_name} {message.chat.last_name} id: {message.chat.id}'
            car, fines_list, df = car.request_car_fines(write_to_sql=False, save_links=True)

            display.stop()
            bot.send_chat_action(message.from_user.id, 'typing')

            if len(fines_list) > 0:
                bot.send_chat_action(message.from_user.id, 'typing')

                with open(f'/home/vladimir/python/telegram_bot/payment_links/{car.sts}.txt', 'r', encoding='UTF-8') as file:
                    links = file.readlines()
                with open(f'/home/vladimir/python/telegram_bot/payment_links/{car.sts}.txt', 'w') as file:
                    file.write('')
                with open(f'/home/vladimir/python/telegram_bot/fines/{message.from_user.id}_fines.txt', 'w') as file:
                    for i, fine in enumerate(car.fines):
                        file.write(f"{fine.document}"
                                   f"\n{fine.date_time}"
                                   f"\n{fine.koap}\n\n")

                [payment_keyboard.add(
                    types.InlineKeyboardButton(f'Оплатить штраф №{i + 1}. Сумма: {car.fines[i].sum} руб.', url=link.replace('\n', '')),
                )
                    for i, link in enumerate(links)]

                payment_keyboard.add(types.InlineKeyboardButton(f'Показать текст', callback_data=f'{message.from_user.id}_fines.txt'))
                bot.send_message(message.from_user.id, f'Нашёл штрафов: {len(fines_list)}'
                                                       f'\nСумма: {int(df["sum"].sum())} рублей'
                                                       f'\n', reply_markup=payment_keyboard)
            else:
                bot.send_message(message.from_user.id, f'Штрафов нет! Ты молодец!', reply_markup=default_keyboard(message))

        except Exception as e:
            bot.send_message(message.from_user.id, f'Произошла ошибка! Попробуйте снова. /check', reply_markup=default_keyboard(message))
            print(e)

        finally:
            if message.from_user.id != 208470137:
                with open('bot_log.txt', 'a') as file:
                    file.write(f'\n{datetime.datetime.now()}\n{car.__dict__}\n')
    else:
        try:
            bot.send_message(message.from_user.id, 'Номер СТС должен состоять из 10ти символов!'
                                                   '\nНапиши "нет", если хочешь остановить проверку')
            bot.register_next_step_handler_by_chat_id(message.chat.id, process_car_check)
        except Exception as e:
            bot.send_message(message.from_user.id, f'Произошла ошибка! Попробуйте снова. /check')
            print(e)


def process_phone_step(message, phone_number):
    try:
        bot.send_message(message.from_user.id, 'Теперь пришли мне номер свидетельства о регистрации (СТС) автомобиля,'
                                               ' который ты хочешь регулярно проверять на наличие штрафов.',
                         reply_markup=sign_up_keyboard(message, phone_number))
        bot.register_next_step_handler_by_chat_id(message.from_user.id, process_user_sign_up, phone_number=phone_number)
    except Exception as e:
        bot.send_message(208470137, e)


def process_user_sign_up(message, phone_number):
    try:
        if message.text == 'Прервать регистрацию':
            return bot.send_message(chat_id=message.from_user.id,
                                    text='Ок. Я забыл твой номер и сделаю вид, что ничего не было...',
                                    reply_markup=default_keyboard(message))

        result = add_telegram_public_user(tg_id=message.from_user.id,
                                          first_name=message.chat.first_name,
                                          last_name=message.chat.last_name,
                                          phone=phone_number,
                                          sts=str(message.text).replace(' ', '')
                                          )
        if result is not None and 'Ты прислал' in result:
            bot.register_next_step_handler_by_chat_id(message.from_user.id, process_phone_step(message, phone_number))

        bot.send_message(message.from_user.id,
                         text=result,
                         reply_markup=default_keyboard(message)
                         )
    except Exception as e:
        bot.send_message(208470137, e)


def process_car_add(message):
    if message.text.lower() in ['нет', 'no', 'ytn', 'yt', 'не', 'yj']:
        bot.send_message(message.from_user.id, 'Ну нет, так нет', reply_markup=settings_keyboard())
        return

    result = add_car_for_check(tg_id=message.from_user.id,
                               sts=str(message.text).replace(' ', '')
                               )
    if 'Ты прислал' in result:
        bot.send_message(message.from_user.id, result)
        bot.register_next_step_handler_by_chat_id(message.from_user.id, process_car_add)
    elif 'Ошибка' in result:
        bot.send_message(message.from_user.id, result + '\nПопробуй снова!')
        bot.register_next_step_handler_by_chat_id(message.from_user.id, process_car_add)
    elif result is None:
        bot.send_message(message.from_user.id, 'Что-то пошло не так... Я не смог добавить авто')
    else:
        bot.send_message(message.from_user.id, result, reply_markup=settings_keyboard())


# --------------------------------------------------------------------------------------------------------------------
# HANDLERS


# Commands handlers
@bot.message_handler(commands=['start'])
def start_bot(message: Message):
    # print(message.json['from'])
    bot.send_message(message.chat.id, f'༼ つ ◕_◕ ༽つ'
                                      f'\nПривет, {message.chat.first_name}!', reply_markup=default_keyboard(message))

    bot.send_message(message.chat.id, #'В целях соблюдения приватности, я не веду никаких записей, но собираю статистику об использования'
                                      #'\nЧтобы полностью удалить введёные Вами данные (включая статистические), удалите переписку со мной'
                                      '\nЧтобы проверить авто нажми или напиши /check')

    add_start_user(message)

    # json = {'message_id': 6052,
    #         'from': {'id': 208470137, 'is_bot': False, 'first_name': 'Vladimir', 'last_name': 'Kulyashov', 'username': 'vovkaperm', 'language_code': 'ru'},
    #         'chat': {'id': 208470137, 'first_name': 'Vladimir', 'last_name': 'Kulyashov', 'username': 'vovkaperm', 'type': 'private'},
    #         'date': 1568211573,
    #         'text': '/start sign_up',
    #         'entities': [{'offset': 0, 'length': 6, 'type': 'bot_command'}]}


@bot.message_handler(commands=['help'])
def help_bot(message: Message):
    bot.send_message(message.chat.id, text=f"༼ つ ◕_◕ ༽つ"
                                           f"\nБот является частью ресурса gtadmin.ru и находится на стадии открытого бета-теста."
                                           f"\nДля обратной связи или для проверки автопарка заполните форму на сайте"

                                           f"\nСписок доступных команд:"
                                           f"\n/start - Запустить бота"
                                           f"\n/check - Проверить один автомобиль или несколько (для зарегистрированных пользователей)"
                                           f"\n/settings - Настройки. Тут можно добавить или убрать авто для проверки"
                                           f"\n/get_stats - Получить статистики по автопарку (требуется регистрация и обратная связь на сайте gtadmin.ru)"
                                           f"\n/stop - Остановить бота"
                                           f"\n/help - Эта справка",

                     reply_markup=default_keyboard(message))


@bot.message_handler(commands=['check'])
def check_one_car(message):
    if message.from_user.id in get_users_dict('telegram_users').keys():
        for sts in get_user_cars(message.from_user.id):
            process_car_check(message, sts)
        return
    else:
        try:
            check_markup = default_keyboard(message)
            check_markup.add('Нет')
            bot.send_message(message.chat.id, '༼ つ ◕_◕ ༽つ'
                                              '\n👌 давай проверим, есть ли у тебя штрафы?'
                                              '\nПришли мне номер свидетельства о регистрации'
                                              '\nОно такое розовое 🐷',
                             reply_markup=check_markup
                             )
            bot.register_next_step_handler_by_chat_id(message.chat.id, process_car_check(message))
        except Exception as e:
            bot.send_message(message.chat.id, e)


@bot.message_handler(commands=['stop'])
def stop_bot(message: Message):
    bot.send_message(message.chat.id, '༼ つ ◕_◕ ༽つ'
                                      '\nЯ удалил все записи о тебе.'
                                      '\nЖаль, что ты уходишь. Напиши мне /start когда снова захочешь пообщаться ')


@bot.message_handler(commands=['get_stats'])
def send_statistics(message: Message):
    if message.from_user.id in get_users_dict('telegram_admin_users').values():
        bot.send_message(message.from_user.id, '༼ つ ◕_◕ ༽つ'
                                               '\nЧего изволите?', reply_markup=stats_keyboard())

    else:
        bot.reply_to(message, 'Обратись к @vovkaperm для доступа к этому разделу')


@bot.message_handler(commands=['sign_up'])
def sign_up_user(message: Message):
    if message.from_user.id in get_users_dict('telegram_users').keys():
        add_car_to_user = types.InlineKeyboardMarkup()
        add_car_to_user.add(types.InlineKeyboardButton('Добавить', callback_data='add_car_to_user'))

        bot.send_message(chat_id=message.from_user.id,
                         text='༼ つ ◕_◕ ༽つ'
                              '\nТы уже зарегистрирован!\nХочешь добавить ещё один автомобиль для проверки?',
                         reply_markup=add_car_to_user)
    else:
        try:
            bot.send_message(message.from_user.id, 'Регистрация нужна, если ты хочешь, чтобы я регулярно проверял наличие у тебя штрафов и оповещал о найденых.'
                                                   '\nНажми кнопку "Продолжить регистрацию".',
                             reply_markup=sign_up_keyboard(message))

        except Exception as e:
            bot.send_message(message.from_user.id, 'Что-то пошло не так... Не могу зарегистрировать тебя'
                                                   '\nПопробуй ещё раз! Если не выйдет, напиши @vovkaperm, он поправит')


@bot.message_handler(commands=['settings'])
def handle_settings(message):
    if message.from_user.id in get_users_dict('telegram_users').keys():
        bot.send_message(message.from_user.id, '༼ つ ◕_◕ ༽つ'
                                               '\nЗдесь можно управлять автомобилями:', reply_markup=settings_keyboard())
    else:
        bot.send_message(message.from_user.id, 'ಠ_ಠ'
                                               '\nДанный раздел доступен только зарегистрированным пользователям!\n'
                                               'Для регистрации отправь /sign_up', reply_markup=default_keyboard(message))


# Other handlers

@bot.message_handler(content_types=['contact'])
def handle_contacts(message):
    if message.from_user.id == message.contact.user_id:
        try:
            bot.send_message(message.from_user.id, message.contact.phone_number)
            bot.register_next_step_handler_by_chat_id(message.chat.id, process_phone_step(message, message.contact.phone_number))
        except Exception as e:
            bot.send_message(208470137, e)


@bot.callback_query_handler(func=lambda callback: True)
def inline_callback_handling(callback):
    for filename in os.listdir('/home/vladimir/python/telegram_bot/fines/'):
        if filename in callback.data:
            with open(f'/home/vladimir/python/telegram_bot/fines/{filename}', 'r', encoding='UTF-8') as file:
                text = file.read()
            bot.send_message(callback.from_user.id, text)

    # Доступно только зарегистрированным пользователям
    if callback.from_user.id in get_users_dict('telegram_users').keys():

        if 'remove_car_from_check' in callback.data:

            car_list_buttons = types.InlineKeyboardMarkup(row_width=2)
            buttons_list = [car_list_buttons.add(
                types.InlineKeyboardButton(car_sts, callback_data=f'remove_{car_sts}'))
                for car_sts in get_user_cars(callback.from_user.id)]

            car_list_buttons.add(types.InlineKeyboardButton('Назад', callback_data='back_to_settings'))
            bot.edit_message_text(chat_id=callback.message.chat.id,
                                  message_id=callback.message.message_id, text="Авто, закреплённые за тобой:",
                                  reply_markup=car_list_buttons)

            if len(buttons_list) == 1:
                bot.answer_callback_query(callback_query_id=callback.id, show_alert=True,
                                          text=
                                          f'༼ つ ◕_◕ ༽つ'
                                          f'\nВнимание!'
                                          f'\nЕсли удалить единственное авто, то я забуду тебя и придётся регистрироваться занова!')
        elif 'show_user_car_list' in callback.data:
            car_list_buttons = types.InlineKeyboardMarkup(row_width=2)

            car_list_buttons.add(types.InlineKeyboardButton('Назад', callback_data='back_to_settings'))
            bot.edit_message_text(chat_id=callback.message.chat.id,
                                  message_id=callback.message.message_id, text=f"Авто, закреплённые за тобой:"
                                                                               f"\n{get_user_cars(callback.from_user.id, return_text=True)}",
                                  reply_markup=car_list_buttons)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'add_car_for_check' in callback.data:
            bot.edit_message_text(text='Пришли мне номер СТС автомобиля, который хочешь добавить'
                                       '\nНапиши "нет", если передумал',
                                  chat_id=callback.from_user.id,
                                  message_id=callback.message.message_id)
            bot.register_next_step_handler_by_chat_id(callback.from_user.id, process_car_add)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        if 'back_to_settings' in callback.data:
            if callback.from_user.id in get_users_dict('telegram_users').keys():
                bot.edit_message_text(chat_id=callback.message.chat.id,
                                      message_id=callback.message.message_id,
                                      text=f'Доступные авто:'
                                           f'\n{get_user_cars(callback.message.chat.id, return_text=True)}',
                                      reply_markup=settings_keyboard())
                bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        for car_sts in get_user_cars(callback.from_user.id):
            if f'remove_{car_sts}' in callback.data:
                remove_car_from_check(car_sts)
                car_list_buttons = types.InlineKeyboardMarkup(row_width=2)
                buttons = [car_list_buttons.add(types.InlineKeyboardButton(car_sts, callback_data=f'remove_{car_sts}')) for car_sts in
                           get_user_cars(callback.from_user.id)]
                if len(buttons) > 0:
                    car_list_buttons.add(types.InlineKeyboardButton('Назад', callback_data='back_to_settings'))
                else:
                    bot.edit_message_text(chat_id=callback.message.chat.id,
                                          message_id=callback.message.message_id,
                                          text='Спасибо, что пользовался моими услугами! Если захочешь снова зарегистрироваться, напиши /sign_up')
                bot.edit_message_reply_markup(chat_id=callback.message.chat.id,
                                              message_id=callback.message.message_id,
                                              reply_markup=car_list_buttons)
                bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        # bot.send_message(callback.from_user.id, 'ಠ_ಠ'
        #                                         '\nДанный раздел доступен только зарегистрированным пользователям!\n'
        #                                         'Для регистрации отправь /sign_up', reply_markup=default_keyboard(callback.message))
        bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

    # Доступно только админам
    if callback.from_user.id in get_users_dict('telegram_admin_users').values():

        for filename in file_names:
            if filename in callback.data:
                send_file(callback.from_user.id, filename)
                bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        if 'btn_1' in callback.data:
            send_stats(callback)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'btn_2' in callback.data:
            upcoming_osago(callback)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'btn_3' in callback.data:
            car_sum_driver(callback)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'btn_4' in callback.data:
            department_sum(callback)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'btn_5' in callback.data:
            paid_and_new_fines(callback)

            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'btn_6' in callback.data:
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=True, text="Temporary unavailable!")

        elif 'btn_7' in callback.data:
            upcoming_service(callback)
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')

        elif 'back_to_menu' in callback.data:
            bot.edit_message_text(chat_id=callback.message.chat.id,
                                  message_id=callback.message.message_id, text="༼ つ ◕_◕ ༽つ Чё тебе ещё нада та ёпта?!",
                                  reply_markup=stats_keyboard())
            bot.answer_callback_query(callback_query_id=callback.id, show_alert=False, text='')


@bot.edited_message_handler(func=lambda message: True)
def echo_edited(message: Message):
    bot.reply_to(message, 'Прости, я плохо разбираюсь в изменениях, тебе придётся начать проверку занова /check :(')


@bot.message_handler(func=lambda message: message.text == 'Прервать регистрацию')
def interrupt_registration(message):
    bot.send_message(chat_id=message.from_user.id,
                     text='Ок. Сделаем вид, что ничего не было...',
                     reply_markup=default_keyboard(message))


@bot.message_handler(func=lambda message: message.text == 'bot_log')
def bot_log(message):
    if message.chat.id == get_users_dict()['Vladimir']:
        bot.send_document(get_users_dict()['Vladimir'], data=open('/home/vladimir/python/bot_log.txt', 'rb'))


@bot.message_handler(content_types=['text'])
def echo_all(message: Message):
    bot.reply_to(message, '༼ つ ◕_◕ ༽つ\n' + message.text.upper())


# --------------------------------------------------------------------------------------------------------------------
# End of Bot logic
# ||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()

# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                certificate=open(WEBHOOK_SSL_CERT, 'r'))

# Build ssl context
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# Start web-server (aiohttp)
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=context,
)
