import dash
from dash import html
import dash_bootstrap_components as dbc

dash.register_page(__name__, path='/about', name='About', title='NewsLens | About')

layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H2('About This Project', className='mb-4')
        ], width=12)
    ]),

    # Creator Section
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Div('Img', style={'fontSize': '4rem'}),
                        ], md=2, className='text-center d-flex align-items-center justify-content-center'),
                        dbc.Col([
                            html.H4('James Vescovo', className='mb-2'),
                            html.P([
                                'Computer Science Student at the University of Denver',
                                html.Br(),
                                html.Small('Expected Graduation: May 2026')
                            ]),
                            html.P(
                                'Passionate about machine learning, data science, and building '
                                'applications that make complex analysis accessible. This project '
                                'combines my interests in NLP and web development to create a tool '
                                'for understanding emotional tone and multi-dimensional news content '
                                'analysis.'
                            ),
                            html.Div([
                                dbc.Badge('Python', color='primary', className='me-1'),
                                dbc.Badge('Machine Learning', color='success', className='me-1'),
                                dbc.Badge('SQL', color='info', className='me-1'),
                                dbc.Badge('Data Visualization', color='warning', className='me-1'),
                            ])
                        ], md=10)
                    ])
                ])
            ], className='shadow-sm mb-4')
        ], lg=10, className='mx-auto')
    ]),

    # Project History Timeline
    dbc.Row([
        dbc.Col([
            html.H4('Project History', className='mb-4'),
            dbc.Card([
                dbc.CardBody([
                    # Timeline entries
                    html.Div([
                        html.Div([
                            html.Div([
                                html.Span('Phase 1', className='badge bg-primary me-2'),
                                html.Strong('Initial Research & Model Development')
                            ]),
                            html.P(
                                'Explored sentiment analysis approaches, comparing rule-based methods (VADER) '
                                'with machine learning classifiers (Naive Bayes, SVM). Built initial models '
                                'and established baseline accuracy metrics using labeled training data.',
                                className='mb-0 ms-5'
                            )
                        ], className='mb-4'),

                        html.Div([
                            html.Div([
                                html.Span('Phase 2', className='badge bg-primary me-2'),
                                html.Strong('Model Evaluation & Comparison')
                            ]),
                            html.P(
                                'Implemented k-fold cross-validation for robust accuracy measurement. '
                                'Developed comprehensive evaluation metrics including precision, recall, '
                                'and F1 scores. Compared VADER and Naive Bayes performance across different text types.',
                                className='mb-0 ms-5'
                            )
                        ], className='mb-4'),

                        html.Div([
                            html.Div([
                                html.Span('Phase 3', className='badge bg-primary me-2'),
                                html.Strong('Web Application Development')
                            ]),
                            html.P(
                                'Built an interactive dashboard using Dash and Bootstrap to make the '
                                'sentiment analysis models accessible through a web interface. Added '
                                'real-time text analysis, visualizations, and model comparison features.',
                                className='mb-0 ms-5'
                            )
                        ], className='mb-4'),

                        html.Div([
                            html.Div([
                                html.Span('Phase 4', className='badge bg-secondary me-2'),
                                html.Strong('News Feed Integration')
                            ]),
                            html.P(
                                'Delivered RSS pipeline integration with GitHub Actions automation, '
                                'OpenAI-powered multi-lens rubric scoring across six analytical '
                                'dimensions, and a dashboard landing page linking to all digest, stats, '
                                'trends, sources, tags, and score lab views.',
                                className='mb-0 ms-5'
                            )
                        ], className='mb-4'),

                        html.Div([
                            html.Div([
                                html.Span('Phase 5', className='badge bg-secondary me-2'),
                                html.Strong('Comparative Analysis'),
                                html.Span(' (Current)', className='fst-italic')
                            ]),
                            html.P(
                                'Building the bridge between the ML models and the LLM lens by running '
                                'traditional classifiers on news articles and comparing their outputs '
                                'with OpenAI rubric scores to understand when classic sentiment '
                                'prediction agrees with multi-dimensional content analysis.',
                                className='mb-0 ms-5'
                            )
                        ], className='mb-4'),
                    ])
                ])
            ], className='shadow-sm mb-4')
        ], lg=10, className='mx-auto')
    ]),

    # Technical Stack
    dbc.Row([
        dbc.Col([
            html.H4('Technical Stack', className='mb-4'),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6('Backend & ML', className='text-primary'),
                            html.Ul([
                                html.Li('Python'),
                                html.Li('Scikit-Learn'),
                                html.Li('NLTK / VADER'),
                                html.Li('OpenAI API'),
                                html.Li('Pandas & NumPy'),
                            ], className='list-unstyled text-muted')
                        ])
                    ], className='h-100')
                ], md=4, className='mb-3'),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6('Web Framework', className='text-primary'),
                            html.Ul([
                                html.Li('Dash by Plotly'),
                                html.Li('Dash Bootstrap Components'),
                                html.Li('Plotly for Visualizations'),
                            ], className='list-unstyled text-muted')
                        ])
                    ], className='h-100')
                ], md=4, className='mb-3'),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H6('Deployment', className='text-primary'),
                            html.Ul([
                                html.Li('DigitalOcean App Platform'),
                                html.Li('GitHub for Version Control'),
                                html.Li('GitHub Actions'),
                            ], className='list-unstyled text-muted')
                        ])
                    ], className='h-100')
                ], md=4, className='mb-3'),
            ])
        ], lg=10, className='mx-auto')
    ]),

    # Contact / Links
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5('Connect', className='mb-3'),
                    html.Div([
                        dbc.Button(
                            [html.I(className='me-2'), 'GitHub'],
                            href='https://github.com/JamesVescovo24',  # Update with your GitHub
                            target='_blank',
                            color='dark',
                            outline=True,
                            className='me-2'
                        ),
                        dbc.Button(
                            [html.I(className='me-2'), 'LinkedIn'],
                            href='https://www.linkedin.com/in/james-vescovo-2b168334b/',  # Update with your LinkedIn
                            target='_blank',
                            color='primary',
                            outline=True,
                            className='me-2'
                        ),
                    ], className='text-center')
                ])
            ], className='shadow-sm')
        ], lg=10, className='mx-auto')
    ], className='mb-4'),

], fluid=True, className='py-4')
