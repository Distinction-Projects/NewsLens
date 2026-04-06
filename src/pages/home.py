import dash
import dash_bootstrap_components as dbc
from dash import html


dash.register_page(__name__, path='/', name='Home', title='NewsLens | Home')

try:
    from src.NewsLens import load_cached_metrics
except ModuleNotFoundError:
    from NewsLens import load_cached_metrics


METRICS = load_cached_metrics()
if METRICS is None:
    raise RuntimeError('Cached metrics could not be loaded')


def _extract_home_metrics(payload):
    """Return model accuracies from either the current or legacy metrics schema."""
    if isinstance(payload, dict) and isinstance(payload.get('datasets'), dict):
        datasets = payload.get('datasets', {})
        default_dataset = payload.get('default_dataset', 'train5')
        dataset_payload = datasets.get(default_dataset) or next(iter(datasets.values()), {})
        models = dataset_payload.get('models', {}) if isinstance(dataset_payload, dict) else {}
    else:
        models = payload.get('models', {}) if isinstance(payload, dict) else {}

    def _acc(model_key):
        model_payload = models.get(model_key, {}) if isinstance(models, dict) else {}
        value = model_payload.get('accuracy', 0.0) if isinstance(model_payload, dict) else 0.0
        return float(value) if isinstance(value, (int, float)) else 0.0

    return {
        'VADER': _acc('vader'),
        'Naive Bayes': _acc('naive bayes'),
        'Support Vector Machine': _acc('svm'),
    }


MODEL_ACCURACIES = _extract_home_metrics(METRICS)
best_model = max(MODEL_ACCURACIES, key=MODEL_ACCURACIES.get)
best_acc = MODEL_ACCURACIES[best_model]
runner_up_acc = sorted(MODEL_ACCURACIES.values(), reverse=True)[1] if len(MODEL_ACCURACIES) > 1 else best_acc
diff = max(best_acc - runner_up_acc, 0.0)


def make_feature_card(icon_class, title, description, link, link_text):
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(html.I(className=icon_class), className='fs-2 text-primary mb-3'),
                html.H5(title, className='card-title text-white'),
                html.P(description, className='card-text text-white'),
                dbc.Button(link_text, href=link, color='outline-primary', size='sm'),
            ],
            className='text-center',
        ),
        className='h-100 shadow-sm',
    )


layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.H1('NewsLens', className='display-4 fw-bold'),
                                html.P(
                                    'A Dash application for AI news monitoring first, with local '
                                    'sentiment-model tooling kept alongside it. The news workflow '
                                    'reads from the external RSS repository at runtime, so daily '
                                    'content refreshes do not require a new deploy.'
                                ),
                                dbc.Button('Open News Digest', href='/news/digest', color='primary', size='lg', className='me-2'),
                                dbc.Button('Workflow Status', href='/news/workflow-status', outline=True, color='secondary', size='lg'),
                            ],
                            className='text-center py-5',
                        )
                    ],
                    width=12,
                )
            ],
            className='mb-5',
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-newspaper',
                            'News Digest',
                            'Inspect the latest upstream articles, filters, and per-article scoring details.',
                            '/news/digest',
                            'Open Digest',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-list-check',
                            'Workflow Status',
                            'Verify freshness, scrape coverage, scoring, and contract health from the live RSS feed.',
                            '/news/workflow-status',
                            'Open Status',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-wave-square',
                            'News Stats',
                            'Review source counts, tag distributions, score bins, and time-based summaries.',
                            '/news/stats',
                            'Open Stats',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-clock-rotate-left',
                            'Snapshot Compare',
                            'Compare the current feed with a frozen historical snapshot from the RSS history archive.',
                            '/news/snapshot-compare',
                            'Compare Snapshots',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
            ],
            className='mb-5',
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H5('How the App Works Now', className='mb-0')),
                                dbc.CardBody(
                                    [
                                        html.P(
                                            'The app is a read-only consumer of the public RSS contract '
                                            'published by the external pipeline. It fetches upstream JSON, '
                                            'normalizes the records, computes light derived stats, and '
                                            'renders Dash pages from cached runtime data.'
                                        ),
                                        html.Ul(
                                            [
                                                html.Li('Upstream JSON changes refresh the app data without rebuilding the image.'),
                                                html.Li('Snapshot mode reads immutable history files by date.'),
                                                html.Li('Code deploys are only needed when the application itself changes.'),
                                            ],
                                            className='mb-0',
                                        ),
                                    ]
                                ),
                            ],
                            className='shadow-sm h-100',
                        )
                    ],
                    lg=7,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H5('Local Model Snapshot', className='mb-0')),
                                dbc.CardBody(
                                    [
                                        *[
                                            html.Div(
                                                [
                                                    html.Div(
                                                        [
                                                            html.Span(model_name, className='fw-bold'),
                                                            html.Span(f'{accuracy:.1%}', className='float-end'),
                                                        ]
                                                    ),
                                                    dbc.Progress(
                                                        value=accuracy * 100,
                                                        color=color,
                                                        className='mb-3',
                                                        style={'height': '10px'},
                                                    ),
                                                ]
                                            )
                                            for (model_name, accuracy, color) in [
                                                ('VADER', MODEL_ACCURACIES['VADER'], 'info'),
                                                ('Naive Bayes', MODEL_ACCURACIES['Naive Bayes'], 'success'),
                                                ('Support Vector Machine', MODEL_ACCURACIES['Support Vector Machine'], 'warning'),
                                            ]
                                        ],
                                        html.Div(
                                            [
                                                html.P('Best performer on the default cached dataset', className='text-muted mb-1 small'),
                                                html.H4(best_model, className='text-primary fw-bold mb-1'),
                                                html.P(f'+{diff:.1%} vs next model' if diff else 'No measurable gap', className='text-success mb-0'),
                                            ],
                                            className='text-center',
                                        ),
                                    ]
                                ),
                            ],
                            className='shadow-sm h-100',
                        )
                    ],
                    lg=5,
                    className='mb-4',
                ),
            ],
            className='mb-5',
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-chart-column',
                            'Model Evaluation',
                            'Compare Naive Bayes, SVM, VADER, and precomputed OpenAI labels across local corpora.',
                            '/evaluation',
                            'View Metrics',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-pen-to-square',
                            'Test Your Text',
                            'Run the local sentiment models on ad hoc text without touching the RSS workflow.',
                            '/text',
                            'Start Testing',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-circle-info',
                            'About',
                            'Read the project history, the technical stack, and the current direction of the app.',
                            '/about',
                            'About This Project',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
                dbc.Col(
                    [
                        make_feature_card(
                            'fa-solid fa-server',
                            'Integration Notes',
                            'Inspect the runtime integration page for current-source, snapshot, and contract details.',
                            '/news/integration',
                            'View Integration',
                        )
                    ],
                    md=6,
                    lg=3,
                    className='mb-4',
                ),
            ]
        ),
    ],
    fluid=True,
    className='py-4',
)
