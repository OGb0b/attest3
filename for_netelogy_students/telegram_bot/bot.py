import os
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from dotenv import load_dotenv
import asyncio
import logging

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
FASTAPI_URL = os.getenv('FASTAPI_URL')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class TaskStates(StatesGroup):
    entering_task_name = State()
    entering_deadline = State()


async def get_user_tasks(user_id: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{FASTAPI_URL}/tasks/{user_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logging.error(f"Error fetching tasks: {e}")
            return None


async def add_new_task(task_data: dict):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(f"{FASTAPI_URL}/tasks", json=task_data) as resp:
                return await resp.json()
        except Exception as e:
            logging.error(f"Error adding task: {e}")
            return None


async def delete_task(task_id: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(f"{FASTAPI_URL}/tasks/{task_id}") as resp:
                return resp.status == 200
        except Exception as e:
            logging.error(f"Error deleting task: {e}")
            return False


@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.answer(
        "Привет! Я бот для управления задачами.\n"
        "Доступные команды:\n"
        "/show_tasks - Показать мои задачи\n"
        "/add_task - Добавить новую задачу\n"
        "/delete_task - Удалить задачу"
    )


@dp.message_handler(commands=["show_tasks"])
async def show_tasks_cmd(message: types.Message):
    user_id = message.from_user.id
    tasks = await get_user_tasks(user_id)

    if not tasks:
        await message.answer("У вас пока нет задач!")
        return

    tasks_text = "\n".join(
        f"{i + 1}. {task['task_name']} (до {task['deadline']}) [ID: {task['id']}]"
        for i, task in enumerate(tasks)
    )

    await message.answer(f"Ваши задачи:\n{tasks_text}")


@dp.message_handler(commands=["add_task"])
async def add_task_cmd(message: types.Message):
    await message.answer("Введите название задачи:")
    await TaskStates.entering_task_name.set()


@dp.message_handler(state=TaskStates.entering_task_name)
async def process_task_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['task_name'] = message.text
    await message.answer("Теперь введите дедлайн в формате ДД.ММ.ГГГГ:")
    await TaskStates.entering_deadline.set()


@dp.message_handler(state=TaskStates.entering_deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    try:
        deadline = message.text.strip()
        # Проверка формата даты
        day, month, year = map(int, deadline.split('.'))
        if len(deadline) != 10 or deadline[2] != '.' or deadline[5] != '.':
            raise ValueError

        async with state.proxy() as data:
            task_data = {
                "user_id": message.from_user.id,
                "username": message.from_user.username or str(message.from_user.id),
                "task_name": data['task_name'],
                "deadline": deadline
            }

        result = await add_new_task(task_data)
        if result:
            await message.answer("Задача успешно добавлена!")
        else:
            await message.answer("Ошибка при добавлении задачи!")

        await state.finish()
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")
        await state.finish()


@dp.message_handler(commands=["delete_task"])
async def delete_task_cmd(message: types.Message):
    user_id = message.from_user.id
    tasks = await get_user_tasks(user_id)

    if not tasks:
        await message.answer("У вас нет задач для удаления!")
        return

    keyboard = InlineKeyboardMarkup()
    for task in tasks:
        keyboard.add(InlineKeyboardButton(
            text=f"Удалить {task['id']}",
            callback_data=f"delete_{task['id']}"
        ))

    await message.answer(
        "Выберите задачу для удаления:",
        reply_markup=keyboard
    )


@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def process_delete_task(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    success = await delete_task(task_id)

    if success:
        await callback.message.answer(f"Задача {task_id} успешно удалена!")
    else:
        await callback.message.answer("Ошибка при удалении задачи!")

    await callback.answer()


async def main():
    await dp.start_polling()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())