import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
try:
    from src.NewsLens import load_cached_metrics
except ModuleNotFoundError:
    from NewsLens import load_cached_metrics
dash.register_page(__name__, name='Model Evaluation', title='Sentiment Analyzer | Model Evaluation')

METRICS_CACHE = load_cached_metrics()
DEFAULT_DATASET = METRICS_CACHE.get("default_dataset", "train5")
DATASET_OPTIONS = [
    {'label': html.Span('Train5 Corpus', style={'margin-right': '30px'}), 'value': 'train5'},
    {'label': html.Span('News Corpus', style={'margin-right': '30px'}), 'value': 'news'},
]
MODEL_OPTIONS = [
    {'label': html.Span('Naive Bayes', style={'margin-right': '30px'}), 'value': 'Naive Bayes'},
    {'label': html.Span('SVM', style={'margin-right': '30px'}), 'value': 'SVM'},
    {'label': html.Span('VADER', style={'margin-right': '30px'}), 'value': 'VADER'},
    {'label': html.Span('OpenAI', style={'margin-right': '30px'}), 'value': 'OpenAI'},
]


def _dataset_metrics(dataset_key):
    datasets = METRICS_CACHE.get("datasets", {})
    return datasets.get(dataset_key) or datasets.get(DEFAULT_DATASET, {})


def _dataset_labels(dataset_key):
    labels = _dataset_metrics(dataset_key).get("labels", ["negative", "neutral", "positive"])
    return labels, [label.title() for label in labels]
### PAGE LAYOUT ###############################################################################################################
layout = dbc.Container([
    # title
    dbc.Row([
        dbc.Col([html.H3(['Model Evaluation'])], width=12, className='row-titles')
    ]),
    # data input
    dbc.Row([
        dbc.Col([], width=3),
        dbc.Col([html.P(['Select an evaluation corpus:'], className='par')]),
        dbc.Col([
            dcc.RadioItems(
                options=DATASET_OPTIONS,
                value=DEFAULT_DATASET,
                persistence=True,
                persistence_type='session',
                id='radio-corpus',
                inline=True
            )
        ], width=6),
        dbc.Col([], width=1)
    ], className='row-content'),
    dbc.Row([
        dbc.Col([], width=3),
        dbc.Col([html.P(['Select a model:'], className='par')]),
        dbc.Col([
            dcc.RadioItems(
                options=MODEL_OPTIONS,
                value='Naive Bayes',
                persistence=True,
                persistence_type='session',
                id='radio-model',
                inline=True
            )
        ], width=6),
        dbc.Col([], width=1)
    ], className='row-content'),
    dbc.Row([
        dbc.Col([], width=2),
        dbc.Col([html.Div(id='evaluation-context', className='text-center text-muted')], width=8),
        dbc.Col([], width=2)
    ], className='row-content'),
    # Accuracy, Precision, Recall, F1 metrics
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Accuracy", className="accuracy-label"),
                    html.H3(id='accuracy-display', children='0.00%', className='text-primary')
                ])
            ], className="text-center")
        ], width=3, className="mx-auto"),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Precision", className="precision-label"),
                    html.H3(id='precision-display', children='0.00%', className='text-success')
                ])
            ], className="text-center")
        ], width=3, className="mx-auto"),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Recall", className="recall-label"),
                    html.H3(id='recall-display', children='0.00%', className='text-warning')
                ])
            ], className="text-center")
        ], width=3, className="mx-auto"),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("F1-Score", className="f1-label"),
                    html.H3(id='f1-display', children='0.00%', className='text-danger')
                ])
            ], className="text-center")
        ], width=3, className="mx-auto")
    ], className='row-content'),
    # Confusion matrix fig
    dbc.Row([
        dbc.Col([], width = 2),
        dbc.Col([
            dcc.Loading(id='p1_1-loading', type='circle', children=dcc.Graph(id='fig-pg1', className='my-graph'))
        ], width = 8),
        dbc.Col([], width = 2)
    ], className='row-content')

    # Metrics bar chart
    ,dbc.Row([
        dbc.Col([], width=2),
        dbc.Col([
            dcc.Graph(id='metrics-bar', className='my-graph')
        ], width=8),
        dbc.Col([], width=2)
    ], className='row-content')
    
])
### PAGE CALLBACKS ###############################################################################################################
def create_confusion_matrix_figure(confusion, labels):
    """Create a Plotly heatmap for the confusion matrix."""
    fig = go.Figure(data=go.Heatmap(
        z=confusion,
        x=labels,
        y=labels,
        colorscale='Greens',
        text=confusion,
        texttemplate="%{text}",
        textfont={"size": 16},
        hovertemplate="Actual: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>"
    ))
    
    fig.update_layout(
        title=dict(text="Confusion Matrix", font=dict(size=18), x=0.5, xanchor='center'),
        xaxis_title="Predicted Label",
        yaxis_title="Actual Label",
        template="plotly_dark",
        height=400,
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    return fig
# Create bar chart for metrics
def create_metrics_bar_chart(precision, recall, f1, labels):
    metrics = ['Precision', 'Recall', 'F1-Score']
    data = [
        go.Bar(name=metrics[0], x=labels, y=precision, marker_color='#636EFA'),
        go.Bar(name=metrics[1], x=labels, y=recall, marker_color='#00CC96'),
        go.Bar(name=metrics[2], x=labels, y=f1, marker_color='#EF553B')
    ]
    fig = go.Figure(data=data)
    fig.update_layout(
        barmode='group',
        title=dict(text="Model Metrics", font=dict(size=18), x=0.5, xanchor='center'),
        yaxis_title="Score",
        xaxis_title="Class",
        template="plotly_dark",
        height=400,
        margin=dict(l=50, r=50, t=80, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def _model_key(model_type):
    name = str(model_type).strip().lower()
    if name in ("naive bayes", "naivebayes", "nb", "multinomialnb"):
        return "naive bayes"
    if name in ("svm", "support vector machine", "support-vector-machine"):
        return "svm"
    if name == "vader":
        return "vader"
    if name == "openai":
        return "openai"
    return name
# Update fig and accuracy
@callback(
    Output(component_id='evaluation-context', component_property='children'),
    Output(component_id='fig-pg1', component_property='figure'),
    Output(component_id='accuracy-display', component_property='children'),
    Output(component_id='precision-display', component_property='children'),
    Output(component_id='recall-display', component_property='children'),
    Output(component_id='f1-display', component_property='children'),
    Output(component_id='metrics-bar', component_property='figure'),
    Input(component_id='radio-corpus', component_property='value'),
    Input(component_id='radio-model', component_property='value')
)
def update_evaluation(dataset_key, model_type):
    """Run the model evaluation and return the confusion matrix, accuracy, and metrics bar chart."""
    labels, labels_display = _dataset_labels(dataset_key)
    dataset_metrics = _dataset_metrics(dataset_key)
    model_key = _model_key(model_type)
    model_metrics = dataset_metrics.get("models", {}).get(model_key)
    context_text = (
        f"Showing {dataset_metrics.get('display_name', 'selected corpus')} metrics. "
        "OpenAI is available on the news corpus using precomputed article sentiment labels."
    )
    if not model_metrics:
        empty = np.zeros((len(labels_display), len(labels_display)))
        fig = create_confusion_matrix_figure(empty, labels_display)
        metrics_bar = create_metrics_bar_chart([0] * len(labels_display), [0] * len(labels_display), [0] * len(labels_display), labels_display)
        return context_text, fig, "N/A", "N/A", "N/A", "N/A", metrics_bar

    confusion = np.asarray(model_metrics.get("confusion", []), dtype=float)
    precision = np.asarray(model_metrics.get("precision", []), dtype=float)
    recall = np.asarray(model_metrics.get("recall", []), dtype=float)
    f1 = np.asarray(model_metrics.get("f1", []), dtype=float)
    accuracy = float(model_metrics.get("accuracy", 0.0))

    fig = create_confusion_matrix_figure(confusion, labels_display)
    accuracy_text = f"{accuracy:.2%}"
    # Calculate macro-averaged metrics for display
    precision_avg = f"{np.mean(precision):.2%}" if hasattr(precision, '__iter__') else f"{precision:.2%}"
    recall_avg = f"{np.mean(recall):.2%}" if hasattr(recall, '__iter__') else f"{recall:.2%}"
    f1_avg = f"{np.mean(f1):.2%}" if hasattr(f1, '__iter__') else f"{f1:.2%}"
    metrics_bar = create_metrics_bar_chart(precision, recall, f1, labels_display)
    return context_text, fig, accuracy_text, precision_avg, recall_avg, f1_avg, metrics_bar
