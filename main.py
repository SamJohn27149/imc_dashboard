# dashapp.py

from math import prod
from dash import Dash, html, Input, Output, dash_table, dcc, State, ctx
from dash.exceptions import PreventUpdate
import pandas as pd
import json
import io
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os
from graph import price_graph, pnl_graph, orderbook_table
from parser import parse_log_file, parse_product_list
TIMESTAMP_MAX = 199900
TIMESTAMP_MIN = 0
# 在输入/调整 timestamp 时，x 轴以该时刻为中心显示的半宽（时间单位与数据一致）
TIMESTAMP_X_VIEW_HALF_SPAN = 5000


external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]
app = Dash(__name__, external_stylesheets=external_stylesheets)




app.layout = html.Div(
    [
        # 'activities', 'logs', 'tradeHistory'])
        dcc.Store(id="activities", data="", storage_type="memory"),
        dcc.Store(id="logs", data=None, storage_type="memory"),
        dcc.Store(id="tradeHistory", data=None, storage_type="memory"),

        html.Div(
            [
                html.Div(
                    dcc.Input(
                        id="directory-input",
                        type="text",
                        placeholder="Enter the derectory path",
                        value = "/home/zhangxin/Documents/imc_dashboard/logfiles"
                    ),
                    className="two columns",
                    style={"margin-top": "6.5vh"},
                ),
                html.Div(
                    dcc.Dropdown(
                        id="log_file_dropdown",
                        options=[],
                        clearable=False,
                        style={"font-size": "12px"},
                    ),
                    className="four columns",
                    style={"margin-top": "6.5vh", "width": "300px"},
                ),
                html.Div(
                    dcc.Dropdown(
                        id="product-dropdown",
                        options=[],
                        clearable=False,
                        style={"font-size": "12px"},
                    ),
                    className="four columns",
                    style={"margin-top": "6.5vh", "width": "300px"},
                ),
                html.Div(
                    html.Button("Load",id="load-button",n_clicks=0),
                    className="one column",
                    style={"margin-top": "6.5vh"},
                ),
            ],
            style={"width": "100%", "display": "inline-block"},
            className="row",
        ),
        html.Div(
            [
                html.Div(
                    children=dcc.Graph(
                        id="mid-price-graph",
                        figure=go.Figure(),
                        style={"height": "50vh"},
                        animate=False,
                    ),
                    className="eight columns",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        #作用是在input窗口旁边有个标签告诉你这个窗口输入什么值
                                        html.Span(
                                            "Timestamp: ",
                                            style={"margin-right": "5px"},
                                        ),
                                        dcc.Input(
                                            id="timestamp-clicked",
                                            type="number",
                                            value=0,
                                            debounce=True,
                                            style={"width": "100px", "margin-right": "50px"},
                                        ),
                                    ],
                                    className="six columns",
                                    style={
                                        "text-align": "center",
                                        "padding-top": "10px",
                                        "display": "flex",
                                        "align-items": "center",
                                        "justify-content": "center",
                                    }
                                ),
                                html.Button(
                                    "<",
                                    id="button-<",
                                    n_clicks=0,
                                    className="one columns",
                                ),
                                html.Button(
                                    ">",
                                    id="button->",
                                    n_clicks=0,
                                    className="one columns",
                                ),
                            ],
                            className="row"
                        ),
                        html.Div(
                            children=[],
                            id="orderbook-table",
                            style={"margin-top": "20px", "margin-left": "10%"},
                            className="ten columns",
                        ),
                    ],
                    className="three columns",
                    style={"margin-left": "5%"},
                ),
            ],
            className="row",
        ),
        html.Div(
            [
                html.Div(
                    dcc.Graph(
                        id="pnl-graph",
                        figure=go.Figure(),
                        style={"height": "50vh", "margin-left": "5%"},
                        animate=False,
                    ),
                    className="eight columns",
                ),
                html.Div(
                    [
                        html.Div(
                            children=[],
                            id="stats-table",
                            className="four columns",
                            style={"margin-top":"60px"},
                        ),
                    ],
                    style={"margin-left": "7%"},
                ),
            ],
            className="row"
        ),
    ]
)


@app.callback(
    Output("log_file_dropdown","options"),
    Input("directory-input","value"),
)
def update_log_file_options(directory):
    if directory:
        logfiles = [f for f in os.listdir(directory) if f.endswith(".log")]
        return [{"lable":f, "value": f} for f in logfiles]
    return []


@app.callback(
    Output("product-dropdown", "options"),
    Input("log_file_dropdown", "value"),
    State("directory-input", "value"),
    prevent_initial_call=True,
)
def update_product_options(log_file, directory):
    activities_json, logs_json, tradeHistory_json = parse_log_file(
        os.path.join(directory, log_file),
    )
    product_list = parse_product_list(activities_json)
    return [{"label": p, "value": p} for p in product_list]


@app.callback(
    Output("activities", "data"),
    Output("logs", "data"),
    Output("tradeHistory", "data"),
    Input("load-button", "n_clicks"),
    State("directory-input", "value"),
    State("log_file_dropdown", "value"),
    State("activities", "data"),
    State("logs", "data"),
    State("tradeHistory", "data"),
    prevent_initial_call=True,
)
def load_logfile_into_stores(
    n_clicks, directory, log_file, activities, logs, trade_history
):
    if not directory or not log_file:
        raise PreventUpdate
    path = os.path.join(directory, log_file)
    if not os.path.isfile(path):
        raise PreventUpdate
    activities_json, logs_json, trade_history_json = parse_log_file(path)
    return activities_json, logs_json, trade_history_json


@app.callback(
    Output("timestamp-clicked","value"),
    Input("button-<","n_clicks"),
    Input("button->","n_clicks"),
    Input('mid-price-graph','clickData'),
    Input('pnl-graph','clickData'),
    State("timestamp-clicked","value"),
)
def update_timestamp(button_minus,button_plus,clickData,pnlClickData,timestamp):
    if "button-<" == ctx.triggered_id:
        if timestamp > TIMESTAMP_MIN:
            timestamp -= 100
    elif "button->" == ctx.triggered_id:
        if timestamp < TIMESTAMP_MAX:
            timestamp +=100
    elif 'mid-price-graph' == ctx.triggered_id and clickData:
        timestamp = clickData['points'][0]['x']
    elif "pnl-graph" == ctx.triggered_id and pnlClickData:
        timestamp = pnlClickData["points"][0]["x"]
    return timestamp


@app.callback(
    Output("mid-price-graph","figure"),
    Input("timestamp-clicked","value"),
    State("mid-price-graph","figure"),
    Input("load-button","n_clicks"),
    Input("product-dropdown","value"),
    Input("activities","data"),
    Input("logs","data"),
    Input("tradeHistory","data"),
)
def update_price_graph(timestamp, fig, load_button, product, activities_json, logs_json, tradeHistory_json):
    if activities_json and logs_json and tradeHistory_json:
        if "load-button" == ctx.triggered_id or "product-dropdown" == ctx.triggered_id:
            fig = price_graph(activities_json, logs_json, tradeHistory_json, product, timestamp)
        fig["layout"]["shapes"][0]["x0"] = timestamp
        fig["layout"]["shapes"][0]["x1"] = timestamp
        # 仅在 timestamp 输入框（或依赖其 value 的按钮）变化时，把 x 轴缩放到该时刻附近
        if ctx.triggered_id == "timestamp-clicked":
            try:
                ts = float(timestamp)
            except (TypeError, ValueError):
                ts = float(TIMESTAMP_MIN)
            half = TIMESTAMP_X_VIEW_HALF_SPAN
            lo = max(TIMESTAMP_MIN, ts - half)
            hi = min(TIMESTAMP_MAX, ts + half)
            if hi <= lo:
                hi = lo + 1
            if hasattr(fig, "update_layout"):
                fig.update_layout(xaxis=dict(range=[lo, hi], autorange=False))
            else:
                xa = fig.setdefault("layout", {}).setdefault("xaxis", {})
                xa["range"] = [lo, hi]
                xa["autorange"] = False
    return fig 

@app.callback(
    Output("pnl-graph","figure"),
    Input("timestamp-clicked","value"),
    State("pnl-graph","figure"),
    Input("load-button","n_clicks"),
    Input("tradeHistory","data"),
    Input("activities","data"),
)
def update_pnl(timestamp, fig, load_button, tradeHistory, activities):
    if activities and tradeHistory:
        if "load-button" == ctx.triggered_id:
            fig = pnl_graph(activities, tradeHistory, timestamp)

        if "shapes" in fig["layout"]:
            fig["layout"]["shapes"][0]["x0"] = timestamp
            fig["layout"]["shapes"][0]["x1"] = timestamp
    return fig


@app.callback(
    Output("orderbook-table", "children"),
    Input("timestamp-clicked", "value"),
    Input("product-dropdown", "value"),
    Input("activities","data"),
)
def update_orderbook(timestamp, product, activities_json):
    if activities_json:
        activities = pd.DataFrame(json.loads(activities_json))
        return orderbook_table(activities, product, timestamp)
    return []




if __name__ == '__main__':
    app.run(debug=True)
