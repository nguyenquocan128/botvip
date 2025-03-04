from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import random
import string
import time
import nest_asyncio
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier

nest_asyncio.apply()

TOKEN = "7791019172:AAGoFhSrvdQlyrJy02hhRq5V1MEUAWPkPaQ"
ADMIN_ID = 5802863171

KEYS = {}
AUTHORIZED_USERS = {ADMIN_ID: "admin"}  # Admin mặc định được đăng nhập
DATA_FILE = "baccarat_data.csv"
LOGIN_HISTORY_FILE = "login_history.csv"

if not os.path.exists(DATA_FILE):
    df = pd.DataFrame(columns=["UserID", "Round", "Result"])
    df.to_csv(DATA_FILE, index=False)

if not os.path.exists(LOGIN_HISTORY_FILE):
    df = pd.DataFrame(columns=["UserID", "Timestamp", "Key"])
    df.to_csv(LOGIN_HISTORY_FILE, index=False)

def generate_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Chào mừng! Nhập /login <key> để bắt đầu.")

async def create_key(update: Update, context: CallbackContext):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Bạn không có quyền tạo key.")
        return
    
    expiration = time.time() + int(context.args[0]) * 3600
    new_key = generate_key()
    KEYS[new_key] = expiration
    await update.message.reply_text(f"🔑 Key: {new_key} (Hết hạn sau {context.args[0]} giờ)")

async def login(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id == ADMIN_ID:
        AUTHORIZED_USERS[user_id] = "admin"
        await update.message.reply_text("Đăng nhập thành công với quyền admin!")
        return
    
    key = context.args[0] if context.args else ""
    if key in KEYS and time.time() < KEYS[key]:
        AUTHORIZED_USERS[user_id] = key
        del KEYS[key]  # Xóa key sau khi sử dụng
        
        df = pd.read_csv(LOGIN_HISTORY_FILE)
        new_entry = pd.DataFrame([{"UserID": user_id, "Timestamp": time.strftime('%Y-%m-%d %H:%M:%S'), "Key": key}])
        df = pd.concat([df, new_entry], ignore_index=True)
        df.to_csv(LOGIN_HISTORY_FILE, index=False)
        
        await update.message.reply_text("Đăng nhập thành công!")
    else:
        await update.message.reply_text("Key không hợp lệ hoặc đã hết hạn!")

def save_result(user_id, result):
    try:
        df = pd.read_csv(DATA_FILE)
        new_round = len(df[df['UserID'] == user_id]) + 1
        new_row = pd.DataFrame([{ "UserID": user_id, "Round": new_round, "Result": result }])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        print(f"✅ Đã lưu kết quả: {result} cho User {user_id}")  # Ghi log
        return df[df['UserID'] == user_id].tail(5)  # Trả về 5 kết quả gần nhất
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu kết quả: {e}")
        return None

async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Bạn chưa đăng nhập. Nhập /login <key> trước!")
        return
    
    result = update.message.text.strip().lower()
    if result in ["b", "p", "t"]:
        mapping = {"b": "Banker", "p": "Player", "t": "Tie"}
        if save_result(user_id, mapping[result]) is not None:
            await update.message.reply_text(f"✅ Đã lưu kết quả: {mapping[result]}")
        else:
            await update.message.reply_text("⚠️ Lỗi khi lưu kết quả!")
    else:
        await update.message.reply_text("⚠️ Nhập: 'b' (Banker), 'p' (Player), hoặc 't' (Tie).")

def encode_result(result):
    return {"Banker": 0, "Player": 1, "Tie": 2}.get(result, -1)

def get_training_data():
    try:
        df = pd.read_csv(DATA_FILE)
        if len(df) < 10:
            print("⚠️ Dữ liệu chưa đủ!")
            return None, None

        df["Encoded_Result"] = df["Result"].apply(encode_result)
        X, y = [], []
        for i in range(len(df) - 5):
            X.append(df["Encoded_Result"].iloc[i:i+5].tolist())
            y.append(df["Encoded_Result"].iloc[i+5])

        return np.array(X), np.array(y)
    except Exception as e:
        print(f"⚠️ Lỗi khi đọc dữ liệu AI: {e}")
        return None, None

def train_ai():
    X, y = get_training_data()
    if X is None:
        return None
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    return model

def predict_next():
    X, _ = get_training_data()
    if X is None:
        return "⚠️ Dữ liệu chưa đủ!"
    model = train_ai()
    if model is None:
        return "⚠️ Không thể huấn luyện AI!"
    last_5_games = X[-1].reshape(1, -1)
    prediction = model.predict(last_5_games)[0]
    return f"🎯 Dự đoán tiếp theo: {["Banker", "Player", "Tie"][prediction]}"

async def predict_command(update: Update, context: CallbackContext):
    await update.message.reply_text(predict_next())

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("createkey", create_key))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot đang chạy...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
