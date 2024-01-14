import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import API_TOKEN
from config import YOUR_ADMIN_USER_ID
from config import DATABASE_NAME

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Создаем подключение к базе данных SQLite
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# Создаем таблицы, если они еще не существуют
cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT NOT NULL,
        photo_url TEXT,
        category_id INTEGER NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
''')

conn.commit()

# ... (добавленные изменения)

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    global menu_markup
    menu_markup = InlineKeyboardMarkup(row_width=2)

    # Добавляем пункты меню
    menu_markup.add(InlineKeyboardButton(text="Каталог", callback_data='menu_catalog'))
    menu_markup.add(InlineKeyboardButton(text="Доставка и оплата", callback_data='menu_delivery'))
    menu_markup.add(InlineKeyboardButton(text="Отзывы", callback_data='menu_reviews'))
    menu_markup.add(InlineKeyboardButton(text="Написать менеджеру", url="https://t.me/Fresko2"))
    menu_markup.add(InlineKeyboardButton(text="Оформить заказ", callback_data='menu_place_order'))
    await bot.send_message(message.from_user.id, "Здравствуйте! Я бот магазина Rio - Поставки из Китая.\nВнизу вы можете выбрать раздел который вас интересует.\nЕсли в списке нет нужного вам вопроса или вы хотите сразу оформить заказ,\nнажмите на кнопку «Написать Менеджеру» и напишите  ваш вопрос, мы ответим вам в течении 5 минут.", reply_markup=menu_markup)
    #await message.answer("Выберите раздел:", reply_markup=markup)

# Создаем состояния для хранения данных о добавляемом товаре
class AddProductStates(StatesGroup):
    CATEGORY = State()
    NAME = State()
    DESCRIPTION = State()
    PHOTOS = State()

# Обработчик команды /add_product
@dp.message_handler(commands=['add_product'])
async def add_product_start(message: types.Message):
    # Проверяем, что отправитель является администратором
    if message.from_user.id == YOUR_ADMIN_USER_ID:
        markup = InlineKeyboardMarkup(row_width=1)

        # Получаем категории из базы данных
        cursor.execute('SELECT id, name FROM categories')
        categories = cursor.fetchall()

        for category in categories:
            markup.add(InlineKeyboardButton(text=category[1], callback_data=f'add_product_{category[0]}'))

        await message.reply("Выберите категорию, в которую хотите добавить товар:", reply_markup=markup)

        # Устанавливаем состояние CATEGORY для пользователя
        await AddProductStates.CATEGORY.set()
    else:
        await message.reply("Вы не имеете доступа к данной команде.")

# Обработчик колбэков от выбора категории при добавлении товара
@dp.callback_query_handler(lambda c: c.data.startswith('add_product_'), state=AddProductStates.CATEGORY)
async def process_add_product_category(callback_query: CallbackQuery, state: FSMContext):
    category_id = int(callback_query.data.split('_')[2])

    # Сохраняем выбранную категорию в состоянии
    await state.update_data(selected_category=category_id)

    await bot.send_message(callback_query.from_user.id, "Введите название для нового товара:")

    # Устанавливаем состояние NAME для пользователя
    await AddProductStates.NAME.set()

# Обработчик текстового сообщения с названием товара
@dp.message_handler(state=AddProductStates.NAME)
async def process_add_product_name(message: types.Message, state: FSMContext):

    # Сохраняем название товара в состоянии
    await state.update_data(product_name=message.text)

    await message.reply("Введите описание для нового товара:")

    # Устанавливаем состояние DESCRIPTION для пользователя
    await AddProductStates.DESCRIPTION.set()

# Обработчик текстового сообщения с описанием товара
@dp.message_handler(state=AddProductStates.DESCRIPTION)
async def process_add_product_description(message: types.Message, state: FSMContext):

    # Сохраняем описание товара в состоянии
    await state.update_data(product_description=message.text)

    await message.reply("Пришлите фотографии для нового товара")

    # Устанавливаем состояние PHOTOS для пользователя
    await AddProductStates.PHOTOS.set()

# Обработчик фотографий товара
@dp.message_handler(state=AddProductStates.PHOTOS, content_types=types.ContentTypes.PHOTO | types.ContentTypes.DOCUMENT)
async def process_add_product_photos(message: types.Message, state: FSMContext):
    # Получаем информацию о товаре из состояния
    data = await state.get_data()
    category_id = data['selected_category']
    product_description = data['product_description']
    product_name = data['product_name']

    # Получаем фотографии товара
    photo = message.photo[-1] if message.photo else None
    document = message.document if message.document and message.document.mime_type.startswith('image/') else None

    if not photo and not document:
        await message.reply("Пожалуйста, пришлите фотографию или документ для нового товара")
        return

    # Получаем URL фотографии товара
    photo_url = photo.file_id if photo else None
    if document:
        file_info = await bot.get_file(document.file_id)
        photo_url = file_info.file_path

    # Добавляем товар в базу данных
    cursor.execute('INSERT INTO products (name, description, photo_url, category_id) VALUES (?, ?, ?, ?)',
                   (product_name, product_description, photo_url, category_id))
    conn.commit()

    await message.reply("Новый товар успешно добавлен!")

    # Очищаем состояние
    await state.finish()

# Обработчик команды /delete_product
@dp.message_handler(commands=['delete_product'])
async def delete_product(message: types.Message):
    # Проверяем, что отправитель является администратором (можно настроить дополнительные условия)
    if message.from_user.id == YOUR_ADMIN_USER_ID:
        await message.reply("Введите ID товара для его удаления:")
        dp.register_message_handler(process_delete_product, content_types=types.ContentTypes.TEXT)
    else:
        await message.reply("Вы не имеете доступа к данной команде.")

async def process_delete_product(message: types.Message):
    product_id = int(message.text)

    # Проверяем существование товара с заданным ID в базе данных
    cursor.execute('SELECT id FROM products WHERE id = ?', (product_id,))
    existing_product = cursor.fetchone()

    if existing_product:
        # Удаляем товар из базы данных
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        await message.reply(f"Товар с ID {product_id} был успешно удалён.")
    else:
        await message.reply(f"Товар с ID {product_id} не найден в базе.")

    # Отменяем обработчик текстовых сообщений для удаления товара
    dp.message_handlers.unregister(process_delete_product)

# Обработчик команды /add_category
@dp.message_handler(commands=['add_category'])
async def add_category(message: types.Message):
    # Проверяем, что отправитель является администратором (можно настроить дополнительные условия)
    if message.from_user.id == YOUR_ADMIN_USER_ID:
        await message.reply("Введите название для новой категории товаров:")
        dp.register_message_handler(process_new_category, content_types=types.ContentTypes.TEXT)
    else:
        await message.reply("Вы не имеете доступа к данной команде.")

async def process_new_category(message: types.Message):
    category_name = message.text

    # Добавляем новую категорию в базу данных
    cursor.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
    conn.commit()

    await message.reply(f"Категория '{category_name}' успешно добавлена в базу.")

    # Отменяем обработчик текстовых сообщений для добавления категории
    dp.message_handlers.unregister(process_new_category)

# Обработчик команды /delete_category
@dp.message_handler(commands=['delete_category'])
async def delete_category(message: types.Message):
    # Проверяем, что отправитель является администратором (можно настроить дополнительные условия)
    if message.from_user.id == YOUR_ADMIN_USER_ID:
        await message.reply("Введите ID категории, которую хотите удалить (удалятся и все товары):")
        dp.register_message_handler(process_delete_category, content_types=types.ContentTypes.TEXT)
    else:
        await message.reply("Вы не имеете доступа к данной команде.")

async def process_delete_category(message: types.Message):
    category_id = int(message.text)

    # Проверяем существование категории с заданным ID в базе данных
    cursor.execute('SELECT id FROM categories WHERE id = ?', (category_id,))
    existing_category = cursor.fetchone()

    if existing_category:
        # Удаляем категорию из базы данных
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        # Удаляем также все товары, связанные с этой категорией
        cursor.execute('DELETE FROM products WHERE category_id = ?', (category_id,))
        conn.commit()
        await message.reply(f"Категория ID: {category_id} - была удалена вместе со всеми связанными с ней товарами.")
    else:
        await message.reply(f"Категория с таким ID: {category_id} - не найдена.")

    # Отменяем обработчик текстовых сообщений для удаления категории
    dp.message_handlers.unregister(process_delete_category)

# ... (добавлены обработчики команд /add_product и /delete_product)

# Обработчик колбэков от меню
@dp.callback_query_handler(lambda c: c.data.startswith('menu_'))
async def process_menu(callback_query: CallbackQuery):
    menu_item = callback_query.data[5:]

    if menu_item == 'catalog':
        # Открываем меню с категориями
        markup = InlineKeyboardMarkup(row_width=1)

        # Получаем категории из базы данных
        cursor.execute('SELECT id, name FROM categories')
        categories = cursor.fetchall()

        if len(categories) > 0:
            # Проверяем, что отправитель является администратором
            if callback_query.from_user.id != YOUR_ADMIN_USER_ID:
                for category in categories:
                    markup.add(InlineKeyboardButton(text=category[1], callback_data=f'category_{category[0]}'))
            else:
                await bot.send_message(callback_query.from_user.id, 'Вы Администратор и можете видеть ID категорий.\nЧтобы удалить категории, введите /delete_category')

                for category in categories:
                    cattext = f'{category[1]} [id: {category[0]}]'
                    markup.add(InlineKeyboardButton(text=cattext, callback_data=f'category_{category[0]}'))

            await bot.send_message(callback_query.from_user.id, "Выберите категорию, чтобы посмотреть товары", reply_markup=markup)
            await callback_query.answer(text=" ")
        else:
            await bot.send_message(callback_query.from_user.id, "Простите, но у нас в магазине пока нет каталога, зайдите позже.")
            await callback_query.answer(text=" ")

    elif menu_item == 'delivery':
        text_delivery = 'Доставка ⤵️\n\n' + \
                        'Доставка в любой город России через Почта России, Сдэк, Боксбери , Авито exmail , DPD или через любой для вас удобный пункт.\n\n' +\
                        'Доставка по Москве : По Москве ваш заказ принесет наш личный курьер, при необходимости поможет с полной настройкой телефона.\n\n' +\
                        'Оплата ⤵️\n' +\
                        'Если ваш заказ оформлен в любой другой город кроме Москвы , то у вас полная предоплата за выбранный вами товар , за доставку уже можете оплатить как вам удобнее , либо сразу либо при получении.\n' +\
                        'Чтоб узнать точную сумму за доставку , напишите нашему менеджеру адрес доставки. Средняя цена 300-500р\n\n' +\
                        'Если вы заказали товар по Москве , то вся оплата происходит после получении вами товара, оплатить можно курьеру наличными или переводом.\n' +\
                        'Доставка на метро 400р.\n' +\
                        'Доставка на Адрес в пределах МКАД 600р.\n' +\
                        'Так же вы можете приехать к нам и проверить желаемый товар.\n' +\
                        'Наш адрес: метро Красносельская , Краснопрудная ул, дом 26, предварительно до приезда напишете менеджеру.'
        await bot.send_message(callback_query.from_user.id, text_delivery, reply_markup=menu_markup, parse_mode="HTML")
        await callback_query.answer(text=" ")

    elif menu_item == 'reviews' or menu_item == 'contact_manager' or menu_item == 'place_order':
        reviews_text = 'Все свежие отзывы публикуем у нас в группе ⤵️\n' + \
                        'https://t.me/mskstoreopt\n' + \
                        'Так же есть фото/ видео отчёты про ваши отправки.\n' + \
                        'Группа ведется почти 2 года и на протяжении всего времени есть отзывы от наших клиентов, так же у нас открыты комментарии в группе.\n' + \
                        'После приобретения у нас товара ,обязательно оставьте нам отзыв, это поможет других клиентам 🙏🤝\n\n' + \
                        'https://t.me/mskstoreopt'
        text = reviews_text if menu_item == 'reviews' else "Написать менеджеру" if menu_item == 'contact_manager' else "Для оформления заказа необходимо написать менеджеру\n(нажать на кнопку и перейти в диалог) и указать какие товары вы хотите приобрести\nОн скинет вам форму для заказа и реквизиты для оплаты"
        if menu_item != 'contact_manager':
            await bot.send_message(callback_query.from_user.id, text, reply_markup=menu_markup, parse_mode="HTML")
        elif menu_item == 'contact_manager':
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(InlineKeyboardButton(text="Написать менеджеру", url="https://t.me/Fresko2"))
            await bot.send_message(callback_query.from_user.id, text, reply_markup=markup, parse_mode="HTML")
        await callback_query.answer(text=" ")

# Обработчик колбэков от выбора категории при добавлении товара
@dp.callback_query_handler(lambda c: c.data.startswith('category_'))
async def process_menu(callback_query: CallbackQuery, state: FSMContext):
    category_id = int(callback_query.data.split('_')[1])

    # Получаем товары для выбранной категории из базы данных
    cursor.execute('SELECT id, name FROM products WHERE category_id = ?', (category_id,))
    products = cursor.fetchall()

    if products:
        markup = InlineKeyboardMarkup(row_width=1)

        for product in products:
            product_id = product[0]
            product_name = product[1]
            markup.add(InlineKeyboardButton(text=product_name, callback_data=f'product_{product_id}'))

        await bot.send_message(callback_query.from_user.id, "Выберите интересующий Вас товар:", reply_markup=markup)
        await callback_query.answer(text=" ")
    else:
        await bot.send_message(callback_query.from_user.id, "В этой категории нет товаров.")
        await callback_query.answer(text=" ")

# Обработчик колбэков от выбора товара
@dp.callback_query_handler(lambda c: c.data.startswith('product_'))
async def show_product_info(callback_query: CallbackQuery):
    product_id = int(callback_query.data.split('_')[1])

    # Получаем информацию о товаре из базы данных
    cursor.execute('SELECT name, description, photo_url FROM products WHERE id = ?', (product_id,))
    product_info = cursor.fetchone()

    if product_info:
        product_name = product_info[0]
        product_description = product_info[1]
        photo_url = product_info[2]

        text = f"<b>{product_name}</b>\n\n{product_description}"

        # Отправляем фотографию и текст описания товара
        await bot.send_photo(callback_query.from_user.id, photo=photo_url, caption=text, parse_mode="HTML")
        await callback_query.answer(text=" ")
    else:
        await bot.send_message(callback_query.from_user.id, "Товар не найден")
        await callback_query.answer(text=" ")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)