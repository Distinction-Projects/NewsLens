import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

dash.register_page(__name__, path='/', name='Home', title='NewsLens | Home')

try:
    from src.NewsLens import load_cached_metrics
except ModuleNotFoundError:
    from NewsLens import load_cached_metrics

METRICS = load_cached_metrics()
if METRICS is None:
    raise RuntimeError('Cached metrics could not be loaded')

def _extract_home_metrics(payload):
    """Return model accuracies for the home page from current or legacy metric schemas."""
    # Current schema: {"default_dataset": "...", "datasets": {"train5": {"models": {...}}}}
    if isinstance(payload, dict) and isinstance(payload.get("datasets"), dict):
        datasets = payload.get("datasets", {})
        default_dataset = payload.get("default_dataset", "train5")
        dataset_payload = datasets.get(default_dataset) or next(iter(datasets.values()), {})
        models = dataset_payload.get("models", {}) if isinstance(dataset_payload, dict) else {}
    else:
        # Legacy schema: {"models": {...}}
        models = payload.get("models", {}) if isinstance(payload, dict) else {}

    def _acc(model_key):
        model_payload = models.get(model_key, {}) if isinstance(models, dict) else {}
        value = model_payload.get("accuracy", 0.0) if isinstance(model_payload, dict) else 0.0
        return float(value) if isinstance(value, (int, float)) else 0.0

    return _acc("vader"), _acc("naive bayes"), _acc("svm")


vader_acc, nb_acc, svm_acc = _extract_home_metrics(METRICS)
best_acc = max(vader_acc, nb_acc, svm_acc)
diff = best_acc - vader_acc

if best_acc == vader_acc:
    best_model = 'VADER'
elif best_acc == nb_acc:
    best_model = 'Naive Bayes'
elif best_acc == svm_acc:
    best_model = 'Support Vector Machine'

def make_feature_card(icon, title, description, link, link_text):
    """Create a consistent feature card."""
    return dbc.Card([
        dbc.CardBody([
            html.Div(icon, className='fs-1 text-primary mb-3'),
            html.H5(title, className='card-title', style={'color': 'white'}),
            html.P(description, className='card-text', style={'color': 'white'}),
            dbc.Button(link_text, href=link, color='outline-primary', size='sm')
        ], className='text-center')
    ], className='h-100 shadow-sm')

layout = dbc.Container([
    # Hero Section
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1('Sentiment Analyzer', className='display-4 fw-bold'),
                html.P(
                    'Detect the emotional tone of text using machine learning. '
                    'Classify text as positive, negative, or neutral with our trained models.'
                ),
                dbc.Button('Try It Now', href='/text', color='primary', size='lg', className='me-2'),
                dbc.Button('View Metrics', href='/evaluation', outline=True, color='secondary', size='lg'),
            ], className='text-center py-5')
        ], width=12)
    ], className='mb-5'),

    # Feature Cards
    dbc.Row([
        dbc.Col([
            make_feature_card(
                '📊',
                'Model Evaluation',
                'View detailed performance metrics including accuracy, precision, recall, and F1 score.',
                '/evaluation',
                'View Metrics'
            )
        ], md=4, className='mb-4'),
        dbc.Col([
            make_feature_card(
                '',
                'About Us',
                'Learn more about the team behind this sentiment analysis tool and our mission.',
                '/about',
                'About Us'
            )
        ], md=4, className='mb-4'),
        dbc.Col([
            make_feature_card(
                '✍️',
                'Test Your Text',
                'Enter your own text and see how the models classify its sentiment in real-time.',
                '/text',
                'Start Testing'
            )
        ], md=4, className='mb-4'),
    ], className='mb-5'),

    # Model Comparison Summary
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5('Quick Comparison: VADER, Naive Bayes, and SVM', className='mb-0')),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.Span('VADER', className='fw-bold'),
                                html.Span(f'{vader_acc:.1%}', className='float-end')
                            ]),
                            dbc.Progress(value=vader_acc * 100, color='info', className='mb-3', style={'height': '10px'}),
                            
                            html.Div([
                                html.Span('Naive Bayes', className='fw-bold'),
                                html.Span(f'{nb_acc:.1%}', className='float-end')
                            ]),
                            dbc.Progress(value=nb_acc * 100, color='success', className='mb-3', style={'height': '10px'}),

                            html.Div([
                                html.Span('SVM', className='fw-bold'),
                                html.Span(f'{svm_acc:.1%}', className='float-end')
                            ]),
                            dbc.Progress(value=svm_acc * 100, color='warning', className='mb-3', style={'height': '10px'}),
                        ], md=8),
                        dbc.Col([
                            html.Div([
                                html.P('Best Performer', className='text-muted mb-1 small'),
                                html.H4(best_model, className='text-primary fw-bold'),
                                html.P(f'+{diff:.1%}' if diff else 'Tied', className='text-success') if diff else None
                            ], className='text-center')
                        ], md=4, className='d-flex align-items-center justify-content-center')
                    ])
                ])
            ], className='shadow-sm')
        ], lg=8, className='mx-auto')
    ])
], fluid=True, className='py-4')
