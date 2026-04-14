
from dash import Dash, html, Input, Output, dash_table, dcc, State, ctx
import pandas as pd
import json
import io
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import threading
import re

def parse_lambda(logs_df): 
    lambda_log_rows = []
    # 每个 timestamp 仅一行：对表按时间排序后单次 iterrows，避免每个 ts 再过滤子表
    for _, row in logs_df.sort_values("timestamp").iterrows():
        timestamp = row["timestamp"]
        raw = row["lambdaLog"]
        try:
            d = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for product,value in d.items():
            # bid_map = value.get("bid") or {}
            # bid_quote_price, bid_quote_volume = next(iter(bid_map.items()))
            # ask_map = value.get("ask") or {}
            # ask_quote_price, ask_quote_volume = next(iter(ask_map.items()))
            # # print(f"product: {product}, bid_quote_price: {bid_quote_price}, bid_quote_volume: {bid_quote_volume}, ask_quote_price: {ask_quote_price}, ask_quote_volume: {ask_quote_volume}")
            # lambda_log_rows.append(
            #     {
            #         'timestamp': timestamp,
            #         'product':   product,
            #         'bid_quote_price': bid_quote_price,
            #         'bid_quote_volume':bid_quote_volume,
            #         'ask_quote_price': ask_quote_price,
            #         'ask_quote_volume':ask_quote_volume,
            #     }
            # )
            if not isinstance(value, dict):
                continue
            bid_map = value.get("bid") or {}
            ask_map = value.get("ask") or {}
            if not isinstance(bid_map, dict):
                bid_map = {}
            if not isinstance(ask_map, dict):
                ask_map = {}
            if bid_map:
                bid_quote_price, bid_quote_volume = next(iter(bid_map.items()))
            else:
                bid_quote_price, bid_quote_volume = None, None
            if ask_map:
                ask_quote_price, ask_quote_volume = next(iter(ask_map.items()))
            else:
                ask_quote_price, ask_quote_volume = None, None
            lambda_log_rows.append(
                {
                    "timestamp": timestamp,
                    "product": product,
                    "bid_quote_price": bid_quote_price,
                    "bid_quote_volume": bid_quote_volume,
                    "ask_quote_price": ask_quote_price,
                    "ask_quote_volume": ask_quote_volume,
                }
            )
    lambda_df = pd.DataFrame(lambda_log_rows)
    return lambda_df

def parse_log_file(log_file,product=""):
    ''''
    path: str
    product: str
    '''
    with open(log_file,"r", encoding="utf-8") as file:
        file_content = file.read()
        file_content_dict = json.loads(file_content)

        activities = file_content_dict["activitiesLog"]
        activities_df = pd.read_csv(io.StringIO(activities), sep=";", header=0)
        activities_json = activities_df.to_json()

        logs = file_content_dict["logs"]
        logs_df = pd.DataFrame(logs)
        logs_json = logs_df.to_json()

        tradeHistory = file_content_dict["tradeHistory"]
        tradeHistory_df = pd.DataFrame(tradeHistory)
        tradeHistory_json = tradeHistory_df.to_json()

        return activities_json, logs_json, tradeHistory_json


def parse_product_list(activities_data):
    """从 activities Store 中取 product 列去重值。

    Store 回调里可能是 None、空串、JSON 字符串，或 Dash 反序列化后的 dict/list。
    空串/坏 JSON 会触发 pd.read_json 的 ValueError: Expected object or value。
    """

    # if isinstance(activities_data, str):
    #     s = activities_data
    #     try:
    #         df = pd.read_json(io.StringIO(s))
    #     except ValueError:
    #         return []
    # else:
    #     return []
    activities_df = pd.read_json(io.StringIO(activities_data))
    product_list = activities_df["product"].dropna().unique()

    # return sorted(str(p) for p in df["product"].dropna().unique())
    return product_list

