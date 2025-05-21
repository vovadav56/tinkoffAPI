from datetime import datetime, timedelta
from typing import List
import os
import pandas as pd
import pymysql
import mysql.connector
from sqlalchemy import create_engine
from tinkoff.invest import Client, CandleInterval, HistoricCandle, ShareResponse

def money_to_float(money) -> float:
    return money.units + money.nano / 1e9

def shares_to_df(shares: List[ShareResponse]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "figi": s.figi,
            "lot": s.lot,
            "currency": s.currency,
            "name": s.name,
            "country": s.country_of_risk_name,
            "sector": s.sector,
        }
        for s in shares
    )

def candles_to_df(candles: List[HistoricCandle], figi: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": c.time,
            "volume": c.volume,
            "open": money_to_float(c.open),
            "close": money_to_float(c.close),
            "high": money_to_float(c.high),
            "low": money_to_float(c.low),
            "figi": figi,
        }
        for c in candles
    )

class TinkoffExtractor:
    def __init__(self, token: str, schema: str, mysql_password: str) -> None:
        self.token = token
        self.schema = schema
        self.mysql_password = mysql_password
        self.engine = create_engine(
            f"mysql+pymysql://root:{mysql_password}@mysql_db:3306/{schema}"
        )

    def test_connection(self) -> None:
        mysql.connector.connect(
            host="mysql_db", user="root", password=self.mysql_password, database=self.schema
        ).close()

    def load_shares(self) -> pd.DataFrame:
        with Client(self.token) as client:
            shares = client.instruments.shares().instruments
        df = shares_to_df(shares)
        df.to_sql("shares", self.engine, if_exists="replace", index=False)
        return df

    def _fetch_candles_chunk(
        self,
        figi_list: List[str],
        start: datetime,
        end: datetime,
        interval: CandleInterval,
    ) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        with Client(self.token) as client:
            for figi in figi_list:
                candles = client.get_all_candles(
                    figi=figi, from_=start, to=end, interval=interval
                )
                if candles:
                    frames.append(candles_to_df(candles, figi))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def load_five_year_candles(self, figis: List[str]) -> pd.DataFrame:
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=365 * 5)
        full_df = self._fetch_candles_chunk(
            figi_list=figis,
            start=from_date,
            end=to_date,
            interval=CandleInterval.CANDLE_INTERVAL_DAY,
        )
        full_df.to_sql("candle_year", self.engine, if_exists="replace", index=False)
        return full_df

if __name__ == "__main__":
    token = os.getenv("TINKOFF_API_TOKEN")
    schema = os.getenv("MYSQL_DATABASE")
    password = os.getenv("MYSQL_ROOT_PASSWORD")

    if not all((token, schema, password)):
        raise RuntimeError("Missing one of required environment variables.")

    extractor = TinkoffExtractor(token, schema, password)
    extractor.test_connection()
    print("✔ Connected to MySQL.")

    print("→ Downloading reference data for shares...")
    shares_df = extractor.load_shares()
    print(f"  • {len(shares_df)} rows written to `shares`.")

    # Фильтрация по IT и materials секторам в РФ
    it_df = shares_df[
        (shares_df["country"] == "Российская Федерация") &
        (shares_df["sector"].str.lower() == "it")
    ]

    materials_df = shares_df[
        (shares_df["country"] == "Российская Федерация") &
        (shares_df["sector"].str.lower() == "materials")
    ]

    if it_df.empty and materials_df.empty:
        raise RuntimeError("Нет подходящих акций из РФ в секторах IT или Materials.")

    all_figis = it_df["figi"].tolist() + materials_df["figi"].tolist()

    print("→ Получение последних свечей для оценки текущих цен...")
    recent_candles_df = extractor._fetch_candles_chunk(
        figi_list=all_figis,
        start=datetime.utcnow() - timedelta(days=3),
        end=datetime.utcnow(),
        interval=CandleInterval.CANDLE_INTERVAL_DAY,
    )

    if recent_candles_df.empty:
        raise RuntimeError("Не удалось получить последние свечи.")

    latest_prices = (
        recent_candles_df.sort_values("time")
        .groupby("figi")
        .tail(1)
        .sort_values("close", ascending=False)
    )

    # top-5 по каждому сектору
    it_top_figis = latest_prices[latest_prices["figi"].isin(it_df["figi"])]
    it_top_figis = it_top_figis["figi"].head(5).tolist()

    materials_top_figis = latest_prices[latest_prices["figi"].isin(materials_df["figi"])]
    materials_top_figis = materials_top_figis["figi"].head(5).tolist()

    combined_figis = it_top_figis + materials_top_figis

    if not combined_figis:
        raise RuntimeError("Не удалось определить топ-акции в IT и Materials секторах.")

    print(f"→ Выбраны figi: {combined_figis}")

    print("→ Downloading 5-year daily candles...")
    candles_df = extractor.load_five_year_candles(combined_figis)
    print(f"  • {len(candles_df)} rows written to `candle_year`.")

    print("✓ Finished.")
