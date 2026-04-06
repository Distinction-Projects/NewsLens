import dash
import dash_bootstrap_components as dbc
from dash import html


dash.register_page(__name__, path='/about', name='About', title='NewsLens | About')


layout = dbc.Container(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2('About This Project', className='mb-4')
                    ],
                    width=12,
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        html.Div('Img', style={'fontSize': '4rem'}),
                                                    ],
                                                    md=2,
                                                    className='text-center d-flex align-items-center justify-content-center',
                                                ),
                                                dbc.Col(
                                                    [
                                                        html.H4('James Vescovo', className='mb-2'),
                                                        html.P(
                                                            [
                                                                'Computer Science Student at the University of Denver',
                                                                html.Br(),
                                                                html.Small('Expected Graduation: May 2026'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'Focused on machine learning, data science, and building '
                                                            'interfaces that make technical analysis easier to inspect. '
                                                            'NewsLens now combines local sentiment experiments with a '
                                                            'read-only AI news workflow driven by an external RSS pipeline.'
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Badge('Python', color='primary', className='me-1'),
                                                                dbc.Badge('Machine Learning', color='success', className='me-1'),
                                                                dbc.Badge('RSS Pipelines', color='info', className='me-1'),
                                                                dbc.Badge('Data Visualization', color='warning', className='me-1'),
                                                            ]
                                                        ),
                                                    ],
                                                    md=10,
                                                ),
                                            ]
                                        )
                                    ]
                                )
                            ],
                            className='shadow-sm mb-4',
                        )
                    ],
                    lg=10,
                    className='mx-auto',
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H4('Project History', className='mb-4'),
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Span('Phase 1', className='badge bg-primary me-2'),
                                                                html.Strong('Initial Research & Model Development'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'Explored sentiment analysis approaches, comparing VADER '
                                                            'with machine learning classifiers such as Naive Bayes and '
                                                            'SVM. Built the first local models and established baseline '
                                                            'metrics using labeled training data.',
                                                            className='mb-0 ms-5',
                                                        ),
                                                    ],
                                                    className='mb-4',
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Span('Phase 2', className='badge bg-primary me-2'),
                                                                html.Strong('Model Evaluation & Comparison'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'Implemented evaluation workflows for accuracy, precision, '
                                                            'recall, and F1 score so the local models could be compared '
                                                            'consistently across corpora.',
                                                            className='mb-0 ms-5',
                                                        ),
                                                    ],
                                                    className='mb-4',
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Span('Phase 3', className='badge bg-primary me-2'),
                                                                html.Strong('Web Application Development'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'Built the Dash interface that exposed model testing, '
                                                            'evaluation views, and interactive visual summaries through a '
                                                            'single web application.',
                                                            className='mb-0 ms-5',
                                                        ),
                                                    ],
                                                    className='mb-4',
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Span('Phase 4', className='badge bg-secondary me-2'),
                                                                html.Strong('News Feed Integration'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'Integrated an external RSS pipeline published through '
                                                            'GitHub Actions, added OpenAI-powered rubric scoring, and '
                                                            'built read-only digest, stats, source, tag, workflow, raw '
                                                            'JSON, and snapshot views that refresh from upstream JSON '
                                                            'without rebuilding the deployment image.',
                                                            className='mb-0 ms-5',
                                                        ),
                                                    ],
                                                    className='mb-4',
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Span('Phase 5', className='badge bg-secondary me-2'),
                                                                html.Strong('Comparative Analysis'),
                                                                html.Span(' (Current)', className='fst-italic'),
                                                            ]
                                                        ),
                                                        html.P(
                                                            'The current direction is to compare traditional sentiment '
                                                            'models against the upstream rubric outputs on news articles, '
                                                            'so the app can show where local classifiers agree with or '
                                                            'diverge from the richer multi-lens news analysis.',
                                                            className='mb-0 ms-5',
                                                        ),
                                                    ],
                                                    className='mb-4',
                                                ),
                                            ]
                                        )
                                    ]
                                )
                            ],
                            className='shadow-sm mb-4',
                        ),
                    ],
                    lg=10,
                    className='mx-auto',
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H4('Technical Stack', className='mb-4'),
                        dbc.Row(
                            [
                                dbc.Col(
                                    [
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H6('Backend & ML', className='text-primary'),
                                                        html.Ul(
                                                            [
                                                                html.Li('Python'),
                                                                html.Li('Scikit-Learn'),
                                                                html.Li('NLTK / VADER'),
                                                                html.Li('OpenAI API'),
                                                                html.Li('Pandas & NumPy'),
                                                            ],
                                                            className='list-unstyled text-muted',
                                                        ),
                                                    ]
                                                )
                                            ],
                                            className='h-100',
                                        )
                                    ],
                                    md=4,
                                    className='mb-3',
                                ),
                                dbc.Col(
                                    [
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H6('Web Framework', className='text-primary'),
                                                        html.Ul(
                                                            [
                                                                html.Li('Dash by Plotly'),
                                                                html.Li('Dash Bootstrap Components'),
                                                                html.Li('Plotly for Visualizations'),
                                                            ],
                                                            className='list-unstyled text-muted',
                                                        ),
                                                    ]
                                                )
                                            ],
                                            className='h-100',
                                        )
                                    ],
                                    md=4,
                                    className='mb-3',
                                ),
                                dbc.Col(
                                    [
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.H6('Deployment & Pipeline', className='text-primary'),
                                                        html.Ul(
                                                            [
                                                                html.Li('DigitalOcean'),
                                                                html.Li('GitHub for Version Control'),
                                                                html.Li('GitHub Actions for RSS publishing'),
                                                            ],
                                                            className='list-unstyled text-muted',
                                                        ),
                                                    ]
                                                )
                                            ],
                                            className='h-100',
                                        )
                                    ],
                                    md=4,
                                    className='mb-3',
                                ),
                            ]
                        ),
                    ],
                    lg=10,
                    className='mx-auto',
                )
            ]
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardBody(
                                    [
                                        html.H5('Connect', className='mb-3'),
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    [html.I(className='me-2'), 'GitHub'],
                                                    href='https://github.com/JamesVescovo24',
                                                    target='_blank',
                                                    color='dark',
                                                    outline=True,
                                                    className='me-2',
                                                ),
                                                dbc.Button(
                                                    [html.I(className='me-2'), 'LinkedIn'],
                                                    href='https://www.linkedin.com/in/james-vescovo-2b168334b/',
                                                    target='_blank',
                                                    color='primary',
                                                    outline=True,
                                                    className='me-2',
                                                ),
                                            ],
                                            className='text-center',
                                        ),
                                    ]
                                )
                            ],
                            className='shadow-sm',
                        )
                    ],
                    lg=10,
                    className='mx-auto',
                )
            ],
            className='mb-4',
        ),
    ],
    fluid=True,
    className='py-4',
)
