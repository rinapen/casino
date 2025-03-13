import xgboost as xgb
import numpy as np
from database.db import models_collection

def save_model_to_mongodb(model):
    """XGBoostモデルをMongoDBに保存"""
    booster = model.get_booster()
    model_json = booster.save_raw("json")
    models_collection.update_one(
        {"name": "casino_winrate_model"},
        {"$set": {"model_data": model_json.decode()}},
        upsert=True
    )
    print("✅ XGBoostモデルをMongoDBに保存しました")


def load_model_from_mongodb():
    """MongoDBからXGBoostモデルをロード。モデルがなければ作成"""
    model_data = models_collection.find_one({"name": "casino_winrate_model"})

    if model_data:
        try:
            model = xgb.Booster()
            model.load_model(bytearray(model_data["model_data"], "utf-8"))
            print("✅ XGBoostモデルをロードしました")
            return model
        except Exception as e:
            print(f"⚠ モデルのロードに失敗: {e}。新しいモデルを作成します。")

    print("⚠ モデルがMongoDBに存在しないため、新規作成します。")

    # **新規モデルの作成と保存**
    model = create_and_train_xgb_model()
    save_model_to_mongodb(model)
    return model


def create_and_train_xgb_model():
    """新しいXGBoostモデルを作成し、ダミーデータで学習"""
    print("🔄 新しいXGBoostモデルを作成中...")

    # **ダミーデータを作成**
    X_dummy = np.random.rand(100, 3)  # 100件のランダムなデータ
    y_dummy = np.random.uniform(5, 95, 100)  # 勝率データ (5%~95%)

    # **モデルの学習**
    model = xgb.XGBRegressor()
    model.fit(X_dummy, y_dummy)

    print("✅ XGBoostモデルを新規作成しました")
    return model