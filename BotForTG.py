import logging
import json
import os
from datetime import datetime, date, timedelta, time
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфиг
TOKEN = "8395798407:AAF0k1Q3IVmNFsA_YlLbahG0jNNiFj70oJ0" 
DAILY_LIMIT = 20
ALLOWED_EMOJI = "🎰"
STARTING_CHIPS = 1000
BET_AMOUNT = 100
DAILY_BONUS = 1000
REFERRAL_BONUS = 3000
DATA_FILE = "/app/data/user_data.json"

def ensure_data_directory():
    data_dir = os.path.dirname(DATA_FILE)
    if data_dir and not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

# Загрузка данных с джейсона
def load_user_data():
    global user_data
    ensure_data_directory()

# Значения выигрышных комбинаций
WINNING_COMBINATIONS = {
    1: {"name": "BAR", "level": "small", "emoji": "🍻", "payout": 150},
    22: {"name": "🍒🍒🍒 Три вишенки", "level": "medium", "emoji": "", "payout": 500},
    43: {"name": "🍋🍋🍋 Три лимона(почти)", "level": "medium", "emoji": "", "payout": 1000},
    64: {"name": "7️⃣7️⃣7️⃣ Три топора", "level": "jackpot", "emoji": "🎰💰", "payout": 10000}
}

# Глобальное хранилище данных
user_data = {}

def get_next_midnight():
    tomorrow = date.today() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min)

def reset_daily_counters():
    today = date.today()
    for user_id, data in list(user_data.items()):
        if 'last_played' not in data or data['last_played'].date() != today:
            data['count'] = 0
            data['last_played'] = datetime.now()

def get_win_info(value):
    return WINNING_COMBINATIONS.get(value)

def save_user_data():
    try:
        # datetime в строки для сохранения
        data_to_save = {}
        for user_id, data in user_data.items():
            data_copy = data.copy()
            
            # datetime объектов в строки
            if 'last_played' in data_copy and isinstance(data_copy['last_played'], datetime):
                data_copy['last_played'] = data_copy['last_played'].isoformat()
            
            if 'last_bonus' in data_copy and isinstance(data_copy['last_bonus'], datetime):
                data_copy['last_bonus'] = data_copy['last_bonus'].isoformat()
            
            if 'last_win' in data_copy and data_copy['last_win'] and isinstance(data_copy['last_win']['time'], datetime):
                data_copy['last_win']['time'] = data_copy['last_win']['time'].isoformat()
            
            data_to_save[user_id] = data_copy
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        logger.info("Данные пользователей сохранены")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")

def load_user_data():
    global user_data
    if not os.path.exists(DATA_FILE):
        logger.info("Данные не найдены, используется новый пустой файл")
        user_data = {}
        return
    
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        # строки обратно в datetime
        user_data = {}
        for user_id, data in raw_data.items():
            if 'last_played' in data and data['last_played']:
                data['last_played'] = datetime.fromisoformat(data['last_played'])
            
            if 'last_bonus' in data and data['last_bonus']:
                data['last_bonus'] = datetime.fromisoformat(data['last_bonus'])
            
            if 'last_win' in data and data['last_win'] and 'time' in data['last_win']:
                data['last_win']['time'] = datetime.fromisoformat(data['last_win']['time'])
            
            user_data[int(user_id)] = data
        
        logger.info("Данные пользователей загружены")
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных: {e}")
        user_data = {}

async def handle_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_daily_counters()
    user_id = update.message.from_user.id
    today = date.today()
    
    # Инициализация данных
    if user_id not in user_data:
        user_data[user_id] = {
            'last_played': datetime.now(), 
            'count': 0,
            'chips': STARTING_CHIPS,
            'wins': {
                'total': 0,
                'small': 0,
                'medium': 0,
                'jackpot': 0
            },
            'last_win': None,
            'total_bet': 0,
            'total_won': 0,
            'last_bonus': None,
            'referrals': 0
        }
        save_user_data()
    
    user = user_data[user_id]
    dice = update.message.dice
    
    # Запрет эмодзи
    if dice.emoji != ALLOWED_EMOJI:
        await update.message.reply_text(
            "❌ Разрешены только слоты 🎰!\n"
            "Другие игры запрещены."
        )
        await update.message.delete()
        save_user_data()
        return
    
    # Обновление времени
    user['last_played'] = datetime.now()
    
    # Проверка дневного лимита
    if user['count'] >= DAILY_LIMIT:
        reset_time = get_next_midnight().strftime('%H:%M:%S')
        await update.message.reply_text(
            f"⛔ Превышен дневной лимит!\n"
            f"Вы можете отправить только {DAILY_LIMIT} 🎰 в день.\n"
            f"Лимит обновится в {reset_time} (полночь)"
        )
        await update.message.delete()
        save_user_data()
        return
    
    # Проверка баланса
    if user['chips'] < BET_AMOUNT:
        await update.message.reply_text(
            f"💸 Нужен ДОДЕП!\n"
            f"Ваш баланс: {user['chips']} фишек\n"
            f"Ставка: {BET_AMOUNT} фишек\n\n"
            f"Узнайте как получить больше фишек через /chips"
        )
        await update.message.delete()
        save_user_data()
        return
    
    # Снимаем ставку
    user['chips'] -= BET_AMOUNT
    user['total_bet'] += BET_AMOUNT
    user['count'] += 1
    
    win_info = get_win_info(dice.value)
    win_amount = 0
    
    # Обработка выигрыша
    if win_info:
        win_type = win_info['level']
        win_amount = win_info['payout']
        
        # Начисляем выигрыш
        if win_amount > 0:
            user['chips'] += win_amount
            user['total_won'] += win_amount
            user['wins'][win_type] += 1
            user['wins']['total'] += 1
            user['last_win'] = {
                'type': win_type,
                'time': datetime.now(),
                'amount': win_amount,
                'value': dice.value
            }
        
        # Специальные сообщения для разных типов выигрышей
        result_message = f"🎰 Результат: {win_info['name']}\n"
        result_message += f"💸 Ставка: -{BET_AMOUNT} фишек\n"
        
        if win_amount > 0:
            result_message += f"💰 Выигрыш: +{win_amount} фишек!\n"
            result_message += f"🏆 Баланс: {user['chips']} фишек"
            
            if win_type == 'jackpot':
                await update.message.reply_animation(
                    animation="https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3aDEzZDZmem42cGpvZnczbjUwN3Nyb3dnM2VmYndzajB2emlmNmh5dCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/rrETJTAUzlWiRCkvck/giphy.gif",
                    caption=result_message
                )
            else:
                await update.message.reply_text(result_message)
        else:
            result_message += f"😢 АХАХАХАХАХА, вы проиграли\n"
            result_message += f"🏆 Баланс: {user['chips']} фишек"
            await update.message.reply_text(result_message)
    else:
        result_message = f"🎰 Результат: Не выигрышная комбинация\n"
        result_message += f"💸 Ставка: -{BET_AMOUNT} фишек\n"
        result_message += f"🏆 Баланс: {user['chips']} фишек"
        await update.message.reply_text(result_message)
    
    logger.info(f"User {user_id}: ставка {BET_AMOUNT}, выигрыш {win_amount}, баланс {user['chips']}")
    save_user_data()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args if context.args else []
    
    #список выигрышных комбинаций для сообщения
    win_list = "\n".join(
        f"{combo['emoji']} {combo['name']} - {combo['payout']} фишек" 
        for combo in WINNING_COMBINATIONS.values() if combo['payout'] > 0
    )
    
    # Проверка рефералки
    referrer_id = None
    referral_bonus_applied = False
    
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        
        # Проверка валидности рефера
        if referrer_id and referrer_id != user_id and referrer_id in user_data:
            # Начисляем бонус рефереру
            user_data[referrer_id]['chips'] += REFERRAL_BONUS
            user_data[referrer_id]['referrals'] += 1
            referral_bonus_applied = True
            
            # Уведомляем реферера
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Новый реферал! Вам начислено {REFERRAL_BONUS} фишек за приглашение!\n"
                         f"💎 Ваш баланс: {user_data[referrer_id]['chips']} фишек"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление рефереру {referrer_id}: {e}")

    # Генерация рефералки
    bot = await context.bot.get_me()
    ref_link = f"https://t.me/{bot.username}?start={user_id}"
    
    # Сообщение для нового реферала
    ref_message = ""
    if referral_bonus_applied:
        ref_message = f"\n\n🎉 Вы зарегистрировались по приглашению! Ваш друг получил {REFERRAL_BONUS} фишек!"
    
    await update.message.reply_text(
        f"🎰 Добро пожаловать в AntiCasino Bot!\n\n"
        f"Это симулятор слотов в котором нет нужды (да и возможности) тратить свои деньги"
        f"💰 Ваш текущий баланс: {user_data[user_id]['chips']} фишек\n"
        f"🎯 Ставка за один прокрут: {BET_AMOUNT} фишек\n\n"
        f"🎲 Правила:\n"
        f"• Работает только эмодзи - 🎰\n"
        f"• Лимит: {DAILY_LIMIT} попыток в день\n"
        f"• Сброс лимита в полночь (00:00)\n\n"
        f"🏆 Выигрышные комбинации:\n{win_list}\n\n"
        f"💎 Получить больше фишек:\n"
        f"1. Ежедневный бонус /daily - {DAILY_BONUS} фишек каждый день!\n"
        f"2. Приглашайте друзей по ссылке:\n{ref_link}\n"
        f"   За каждого приглашенного друга вы получаете {REFERRAL_BONUS} фишек!\n\n"
        f"Отправьте 🎰 для игры!{ref_message}"
    )
    save_user_data()

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_daily_counters()
    user_id = update.message.from_user.id
    
    if user_id in user_data:
        data = user_data[user_id]
        reset_time = get_next_midnight().strftime('%H:%M:%S')
        
        win_info = ""
        if data['wins']['total'] > 0:
            win_info = (
                f"• Всего выигрышей: {data['wins']['total']}\n"
                f"• Малых: {data['wins']['small']}\n"
                f"• Средних: {data['wins']['medium']}\n"
                f"• Джекпотов: {data['wins']['jackpot']}\n"
            )
            
            if data['last_win']:
                win_name = WINNING_COMBINATIONS[data['last_win']['value']]['name']
                last_time = data['last_win']['time'].strftime('%d.%m.%Y %H:%M')
                win_info += f"• Последний выигрыш: {win_name} ({last_time})\n"
        
        await update.message.reply_text(
            f"📊 Ваша игровая статистика:\n"
            f"• Баланс: {data['chips']} фишек\n"
            f"• Попыток сегодня: {data['count']}/{DAILY_LIMIT}\n"
            f"• Сброс лимита: {reset_time}\n"
            f"• Всего поставлено: {data['total_bet']} фишек\n"
            f"• Всего выиграно: {data['total_won']} фишек\n"
            f"• Приглашено друзей: {data.get('referrals', 0)}\n\n"
            f"🎰 Статистика выигрышей:\n"
            f"{win_info or '• Пока нет выигрышей'}\n\n"
            f"🔗 Ваша реферальная ссылка:\n{ref_link}\n"
            f"💎 За каждого приглашенного друга вы получаете {REFERRAL_BONUS} фишек!"
        )
    else:
        await update.message.reply_text(
            "Вы еще не начинали играть!\n"
            f"Ваш стартовый баланс: {STARTING_CHIPS} фишек\n"
            "Отправьте 🎰 для начала игры!"
        )
    save_user_data()

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id in user_data:
        chips = user_data[user_id]['chips']
        await update.message.reply_text(
            f"💰 Ваш текущий баланс: {chips} фишек\n"
            f"💸 Ставка за игру: {BET_AMOUNT} фишек\n\n"
            f"Отправьте 🎰 для игры!"
        )
    else:
        await update.message.reply_text(
            f"💰 Ваш текущий баланс: {STARTING_CHIPS} фишек (стартовый)\n"
            f"💸 Ставка за игру: {BET_AMOUNT} фишек\n\n"
            f"Отправьте 🎰 для начала игры!"
        )
    save_user_data()

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    today = datetime.now().date()
    
    user = user_data[user_id]
    
    # Проверка получал ли пользователь дейлик
    if 'last_bonus' in user and user['last_bonus'] and user['last_bonus'].date() == today:
        next_bonus_time = (user['last_bonus'] + timedelta(days=1)).strftime('%d.%m.%Y %H:%M')
        await update.message.reply_text(
            f"⏳ Вы уже получали бонус сегодня!\n"
            f"Следующий бонус будет доступен после {next_bonus_time}"
        )
        save_user_data()
        return
    
    # Начисление дейлика
    user['chips'] += DAILY_BONUS
    user['last_bonus'] = datetime.now()
    
    await update.message.reply_text(
        f"🎁 Получен ежедневный бонус: +{DAILY_BONUS} фишек!\n"
        f"💰 Ваш баланс: {user['chips']} фишек\n\n"
        f"Заходите завтра за новым бонусом!"
    )
    save_user_data()

async def chips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    balance = user_data.get(user_id, {}).get('chips', STARTING_CHIPS)

    
    await update.message.reply_text(
        "💎 Как получить больше фишек:\n\n"
        f"1. Ежедневный бонус /daily - {DAILY_BONUS} фишек каждый день!\n"
        f"2. Выигрывайте в играх 🎰 (отправьте эмодзи 🎰)\n"
        f"3. Приглашайте друзей по ссылке:\n{ref_link}\n"
        f"   За каждого приглашенного друга вы получаете {REFERRAL_BONUS} фишек!\n\n"
        f"💰 Ваш текущий баланс: {balance} фишек"
    )
    save_user_data()

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_daily_counters()
    
    # список игроков
    players = []
    for user_id, data in user_data.items():
        try:
            user = await context.bot.get_chat(user_id)
            name = user.username or user.first_name or f"User {user_id}"
            players.append((name, data['chips'], data.get('referrals', 0)))
        except:
            logger.warning(f"Couldn't get info for user {user_id}")
            players.append((f"User {user_id}", data['chips'], data.get('referrals', 0)))

    if not players:
        await update.message.reply_text("Пока нет активных игроков!")
        return
    
    # сортировка по балансу
    players.sort(key=lambda x: x[1], reverse=True)
    
    # Формируем сообщение
    message = "🏆 Топ игроков по балансу:\n\n"
    for i, (name, balance, refs) in enumerate(players[:10], 1):
        message += f"{i}. {name}: {balance} фишек (Рефералов: {refs})\n"
    
    await update.message.reply_text(message)
    save_user_data()

async def add_chips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # добавить проверку на админа(по юзер айди???)
    is_admin = True  # Пока все админы но никто об этом не знает
    
    if not is_admin:
        await update.message.reply_text("❌ Эта команда только для администраторов!")
        return
    
    # Парсим аргументы: /add_chips [user_id] [amount]
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /add_chips [user_id] [amount]")
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        
        if target_user_id not in user_data:
            user_data[target_user_id] = {
                'last_played': datetime.now(), 
                'count': 0,
                'chips': STARTING_CHIPS,
                'wins': {'total': 0, 'small': 0, 'medium': 0, 'jackpot': 0},
                'last_win': None,
                'total_bet': 0,
                'total_won': 0,
                'last_bonus': None,
                'referrals': 0
            }
        
        user_data[target_user_id]['chips'] += amount
        await update.message.reply_text(
            f"✅ Пользователю {target_user_id} добавлено {amount} фишек\n"
            f"Новый баланс: {user_data[target_user_id]['chips']} фишек"
        )
        save_user_data()
    except ValueError:
        await update.message.reply_text("Ошибка: Некорректные аргументы")

def main():
    # Загрузка данных при запуске
    load_user_data()
    
    # Создание Application
    application = Application.builder().token(TOKEN).build()

    # обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("chips", chips))
    application.add_handler(CommandHandler("daily", daily_bonus))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("add_chips", add_chips))
    
    # Обработчик эмодзи
    application.add_handler(MessageHandler(filters.Dice.ALL, handle_dice))

    # месадж об успешном запуске бота с обработкой завершения
    try:
        logger.info("Casino Bot запущен и готов к игре!")
        application.run_polling()
    finally:
        save_user_data()

if __name__ == "__main__":
    main()