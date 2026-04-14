# graph.py

from dash import Dash, html, Input, Output, dash_table, dcc, State, ctx
import pandas as pd
import json
import io
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
import threading
from io import StringIO
from parser import parse_lambda

def price_graph(activities_json, logs_json, tradeHistory_json, product, timestamp):

    # 绘制订单薄信息和wall_mid 
    activities = pd.read_json(StringIO(activities_json))
    activities_product = activities[activities['product'] == product]
    activities_product['wall_bid'] = activities_product[['bid_price_1','bid_price_2','bid_price_3']].min(axis=1, skipna=True)
    activities_product['wall_ask'] = activities_product[['ask_price_1','ask_price_2','ask_price_3']].max(axis=1, skipna=True)
    activities_product['wall_mid'] = (activities_product['wall_bid'] + activities_product['wall_ask']) / 2

    fig = px.line(
    activities_product, x="timestamp", y=["wall_mid", "mid_price"], title="Price Over Time"
    )   
    fig.update_traces(selector=dict(name="mid_price"), line=dict(color="black"))
    fig.update_traces(selector=dict(name="wall_mid"), line=dict(color="#2563eb"))

    _bid_color = "#16a34a"
    _ask_color = "#dc2626"
    _bid_sizes = [14, 18, 22]
    _ask_sizes = [14, 18, 22]
    for price, size in zip(
        ["bid_price_1", "bid_price_2", "bid_price_3"],
        _bid_sizes,
    ):
        fig.add_trace(
            go.Scatter(
                x=activities_product["timestamp"],
                y=activities_product[price],
                mode="markers",
                name=price,
                marker=dict(color=_bid_color, size=size, line=dict(width=0)),
                hovertemplate="Timestamp: %{x}<br>Price: %{y}<br>Volume: %{text}",
                text=activities_product[price.replace("price", "volume")],
                visible="legendonly",
            )
        )
    for price, size in zip(
        ["ask_price_1", "ask_price_2", "ask_price_3"],
        _ask_sizes,
    ):
        fig.add_trace(
            go.Scatter(
                x=activities_product["timestamp"],
                y=activities_product[price],
                mode="markers",
                name=price,
                marker=dict(color=_ask_color, size=size, line=dict(width=0)),
                hovertemplate="Timestamp: %{x}<br>Price: %{y}<br>Volume: %{text}",
                text=activities_product[price.replace("price", "volume")],
                visible="legendonly",
            )
        )

    # 绘制我们的挂单信息
    logs = pd.read_json(StringIO(logs_json))
    lambdaLog_df = parse_lambda(logs)

    _lambda_ok = not lambdaLog_df.empty and "product" in lambdaLog_df.columns # 要判断当前lambdalog不为空且包含所选品种，否则索引报错
    lamdaLog_product = (lambdaLog_df[lambdaLog_df['product']==product] if _lambda_ok else pd.DataFrame())
    
    if _lambda_ok and not lamdaLog_product.empty:
        for quote in ['bid_quote_price', 'ask_quote_price']:
            fig.add_trace(
                go.Scatter(
                    x=lamdaLog_product['timestamp'],
                    y=lamdaLog_product[quote],
                    mode='markers',
                    name=quote,
                    marker=dict(
                        color="#000000", 
                        size=11, 
                        line=dict(width=0)),

                    hovertemplate="Timestamp: %{x}<br>Quote_Price: %{y}<br>Volume: %{text}",
                    text=lamdaLog_product[quote.replace("price","volume")],
                    visible="legendonly",
                )
            )
        # 

    # 绘制成交信息
    tradeHistory = pd.read_json(StringIO(tradeHistory_json))
    tradeHistory_product = tradeHistory[tradeHistory['symbol']==product]
    market_trades = tradeHistory_product[
        (tradeHistory_product['buyer'] != "SUBMISSION") & (tradeHistory_product["seller"] != "SUBMISSION")
    ]
    own_trades = tradeHistory_product[
        (tradeHistory_product["buyer"] == "SUBMISSION") | (tradeHistory_product["seller"] == "SUBMISSION")
    ]

    if not market_trades.empty:
        mt_agg = (
            market_trades.groupby(["timestamp", "price"], as_index=False)
            .agg(
                qty_sum=("quantity", "sum"),
                qty_list=("quantity", list),
                )
            )
        def _fmt_qty_expr(vals):
            vals = list(vals)
            if not vals:
                return "Qty=0"
            if len(vals) == 1:
                return f"Qty={vals[0]}"
            expr = "+".join(str(v) for v in vals)
            return f"Qty={expr}={sum(vals)}"
            
        mt_agg["qty_text"] = mt_agg["qty_list"].apply(_fmt_qty_expr)


        # fig.add_trace(
        #     go.Scatter(
        #         x=market_trades["timestamp"],
        #         y=market_trades["price"],
        #         mode="markers",
        #         name="market_trades",
        #         marker=dict(
        #             color="#2563eb",
        #             size=8,
        #             symbol="star",
        #             line=dict(width=0),
        #             opacity=0.7,
        #         ),
        #         hovertemplate="Timestamp: %{x}<br>Price: %{y}<br>Qty: %{text}<extra></extra>",
        #         text=market_trades["quantity"],
        #         visible="legendonly",
        #     )
        # )
        fig.add_trace(
            go.Scatter(
                x=mt_agg["timestamp"],
                y=mt_agg["price"],
                mode="markers",
                name="market_trades",
                marker=dict(
                    color="#2563eb",
                    size=8,
                    symbol="star",
                    line=dict(width=0),
                    opacity=0.7,
                ),
                hovertemplate="Timestamp: %{x}<br>Price: %{y}<br>Qty: %{text}<extra></extra>",
                text=mt_agg["qty_text"],
                visible="legendonly",
            )
        )

    if not own_trades.empty:
        fig.add_trace(
            go.Scatter(
                x=own_trades["timestamp"],
                y=own_trades["price"],
                mode="markers",
                name="own_trades",
                marker=dict(
                    color="#fff176",
                    size=8,
                    symbol="cross",
                    line=dict(width=1, color="#ffeb3b"),
                    
                ),
                hovertemplate="Timestamp: %{x}<br>Price: %{y}<br>Qty: %{text}<extra></extra>",
                text=own_trades["quantity"],
                visible="legendonly",
            )
        )
    
    # 计算挂单成交概率
    # lam = lamdaLog_product.copy()
    # lam["bid_quote_price"] = pd.to_numeric(lam["bid_quote_price"], errors="coerce") # 把字符串"10007"转化为数字10007方便后续比较
    # lam["ask_quote_price"] = pd.to_numeric(lam["ask_quote_price"], errors="coerce") 

    # own = own_trades.copy()
    # own["price"] = pd.to_numeric(own["price"], errors="coerce")

    # # 每个 timestamp 对应的 own trade 成交价集合
    # prices_by_ts = own.groupby("timestamp")["price"].apply(lambda s: set(s.dropna()))

    # # 逐行判断：own trade price 是否等于 quote price
    # lam["bid_filled"] = lam.apply(
    #     lambda r: r["bid_quote_price"] in prices_by_ts.get(r["timestamp"], set()),
    #     axis=1,
    # )
    # lam["ask_filled"] = lam.apply(
    #     lambda r: r["ask_quote_price"] in prices_by_ts.get(r["timestamp"], set()),
    #     axis=1,
    # )

    # n_black = lam["bid_quote_price"].notna().sum() + lam["ask_quote_price"].notna().sum()
    # n_matched = lam["bid_filled"].sum() + lam["ask_filled"].sum()
    # # 计算成交概率
    # p = n_matched / n_black if n_black else 0.0   
    # 计算挂单成交概率（bid/ask 列可能缺一或全无）
    n_black = 0
    n_matched = 0
    p = 0.0
    _has_ts = "timestamp" in lamdaLog_product.columns
    _has_bid = "bid_quote_price" in lamdaLog_product.columns
    _has_ask = "ask_quote_price" in lamdaLog_product.columns
    if not lamdaLog_product.empty and _has_ts and (_has_bid or _has_ask):
        lam = lamdaLog_product.copy()
        if _has_bid:
            lam["bid_quote_price"] = pd.to_numeric(
                lam["bid_quote_price"], errors="coerce"
            )
        if _has_ask:
            lam["ask_quote_price"] = pd.to_numeric(
                lam["ask_quote_price"], errors="coerce"
            )
        own = own_trades.copy()
        own["price"] = pd.to_numeric(own["price"], errors="coerce")
        if not own.empty:
            prices_by_ts = own.groupby("timestamp")["price"].apply(
                lambda s: set(s.dropna())
            )
        else:
            prices_by_ts = {}
        if _has_bid:
            lam["bid_filled"] = lam.apply(
                lambda r: r["bid_quote_price"]
                in prices_by_ts.get(r["timestamp"], set()),
                axis=1,
            )
            n_black += lam["bid_quote_price"].notna().sum()
            n_matched += int(lam["bid_filled"].sum())
        if _has_ask:
            lam["ask_filled"] = lam.apply(
                lambda r: r["ask_quote_price"]
                in prices_by_ts.get(r["timestamp"], set()),
                axis=1,
            )
            n_black += lam["ask_quote_price"].notna().sum()
            n_matched += int(lam["ask_filled"].sum())
        p = n_matched / n_black if n_black else 0.0
    
        fig.add_annotation(
            x=0.99, y=0.99,
            xref="paper", yref="paper",
            xanchor="right", yanchor="top",
            text=f"挂单次数: {n_black}<br>挂单成交次数: {n_matched}<br>成交概率: {p:.2%}",
            showarrow=False,
            align="right",
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor="rgba(0,0,0,0.25)",
            borderwidth=1,
        )

    # 绘制指标信息



    
    fig.add_vline(x=timestamp, line_width=1, line_dash="dash", line_color="black")

    return fig


def pnl_graph(activities_json, tradeHistory_json,timestamp):
    activities = pd.read_json(StringIO(activities_json))
    tradeHistory = pd.read_json(StringIO(tradeHistory_json))

    fig = go.Figure()
    # 单品种pnl
    for product in activities['product'].unique():
        activities_product = activities[activities['product'] == product]
        fig.add_trace(
            go.Scatter(
                x = activities_product['timestamp'],
                y = activities_product['profit_and_loss'],
                mode = 'lines',
                name = f"{product} PnL"
            )
        )
    # total pnl
    total_pnl = activities.groupby('timestamp')['profit_and_loss'].sum()
    fig.add_trace(
        go.Scatter(
            x = total_pnl.index,
            y = total_pnl.values,
            mode = 'lines',
            name = 'Total PnL',
        )
    )
    fig.update_layout(xaxis_title="Timestamp", yaxis_title="PnL")
    fig.add_vline(x=timestamp, line_width=1, line_dash="dash", line_color="black")
    fig.update_xaxes(spikemode="across")

    for product in tradeHistory['symbol'].unique():
        if product == 'ORCHIDS' and 'orchids_position' in tradeHistory.columns:  # 硬编码，需要更改
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df["orchids_position"],
                    mode="lines",
                    name=f"{product} Position",
                    yaxis="y2",
                    hovertemplate="Timestamp: %{x}<br>Position: %{y}",
                )
            )
        else:
            tradeHistory_product = tradeHistory[tradeHistory['symbol'] == product]
            own_trades = tradeHistory_product[
                (tradeHistory_product['buyer'] == 'SUBMISSION') | (tradeHistory_product['seller'] == 'SUBMISSION') 
            ].copy()
            own_trades["volume"] = own_trades.apply(
                lambda x: (
                    x["quantity"] if x["buyer"] == "SUBMISSION" else -x['quantity']
                ),
                axis = 1,
            )
            position = own_trades[["timestamp","volume"]].copy()

            if len(position) > 0:
                timestamp_min = min(own_trades["timestamp"].to_numpy())
                timestamp_max = max(own_trades["timestamp"].to_numpy())
                position = position.groupby("timestamp").sum().reset_index()
                position = (
                    position.set_index("timestamp")
                    .reindex(range(timestamp_min, timestamp_max + 1, 100), fill_value=0)
                    .reset_index()
                )
                position = position.groupby("timestamp").sum().reset_index()
                position = position.set_index("timestamp")
                position = position["volume"]

                fig.add_trace(
                    go.Scatter(
                        x=position.index,
                        y=position.values.cumsum(),
                        mode="lines",
                        name=f"{product} Position",
                        yaxis="y2",
                        hovertemplate="Timestamp: %{x}<br>Position: %{y}",
                        visible="legendonly",
                    )
                )
    fig.update_layout(
        yaxis1=dict(
            title="PnL",
        ),
        yaxis2=dict(title="Position", overlaying="y", side="right"),
    )

    return fig
            

   
