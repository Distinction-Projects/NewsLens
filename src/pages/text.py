"""
FIXED VERSION of text.py
Key fixes:
1. Added comprehensive error handling
2. Added data loading validation
3. Fixed callback to show errors properly
"""

from pathlib import Path

import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc

try:
    from src.NewsLens import (
        preprocess,
        prebuilt_model,
        vader_score,
        predict_cached,
        predict_score_cached,
        DATA_PATH,
    )
except ModuleNotFoundError:
    from NewsLens import (
        preprocess,
        prebuilt_model,
        vader_score,
        predict_cached,
        predict_score_cached,
        DATA_PATH,
    )

dash.register_page(__name__, path='/text', name='Test Your Text', title='NewsLens | Test Your Text')

# Validate training data availability for cache warmup
DATA_LOADED = False
DATA_ERROR = None

try:
    data_path = Path(DATA_PATH)
    DATA_LOADED = data_path.exists()
    if not DATA_LOADED:
        DATA_ERROR = f"Could not find '{data_path}'. Make sure the file exists."
except FileNotFoundError:
    DATA_ERROR = f"Could not find '{data_path}'. Make sure the file exists."
except Exception as e:
    DATA_ERROR = f"{type(e).__name__}: {str(e)}"

layout = dbc.Container([
    dbc.Row([
        dbc.Col([html.H3('Test Your Own Text')], width=12, className='row-titles')
    ]),
    
    # Show error if data didn't load
    dbc.Row([
        dbc.Col([
            dbc.Alert(
                [html.I(className="fas fa-exclamation-triangle me-2"), DATA_ERROR],
                color="danger",
                is_open=not DATA_LOADED
            )
        ], width=12)
    ]) if not DATA_LOADED else html.Div(),
    
    dbc.Row([
        dbc.Col([], width=2),
        dbc.Col([
            html.P('Enter your text below and select a model to analyze its sentiment.'),
            dcc.Textarea(
                id='user-text',
                style={
                    'width': '100%', 'height': 120,
                    'backgroundColor': '#212529', 'color': 'white',
                    'border': '1px solid #ced4da', 'padding': '8px', 'borderRadius': '4px'
                },
                placeholder='Type your text here...'
            ),
            html.Br(),
            dcc.RadioItems(
                options=[
                    {'label': html.Span('Naive Bayes', style={'marginRight': '30px'}), 'value': 'Naive Bayes'},
                    {'label': html.Span('SVM', style={'marginRight': '30px'}), 'value': 'SVM'},
                    {'label': html.Span('VADER', style={'marginRight': '30px'}), 'value': 'VADER'}
                ],
                value='Naive Bayes',
                id='model-choice',
                inline=True
            ),
            html.Br(),
            dbc.Button('Analyze', id='analyze-btn', color='primary', disabled=not DATA_LOADED),
            html.Br(), html.Br(),
            html.Div(id='analysis-result')
        ], width=8),
        dbc.Col([], width=2)
    ])
])


@callback(
    Output('analysis-result', 'children'),
    Input('analyze-btn', 'n_clicks'),
    State('user-text', 'value'),
    State('model-choice', 'value'),
    prevent_initial_call=True
)
def analyze_text(n_clicks, user_text, model_choice):
    try:
        # Validate data is loaded
        if not DATA_LOADED:
            return dbc.Alert(f'Training data not available: {DATA_ERROR}', color='danger')
        
        # Validate input
        if not user_text or not user_text.strip():
            return dbc.Alert('Please enter some text to analyze.', color='warning')
        
        # Preprocess input
        processed = preprocess(user_text)
        
        if not processed or not processed.strip():
            return dbc.Alert(
                'After removing stopwords, no meaningful words remain. Try a longer sentence.',
                color='warning'
            )
        
        # Model prediction
        if model_choice == 'VADER':
            pred = prebuilt_model([processed])[0]
            score = vader_score(processed)
        else:
            # For NB/SVM use cached models to avoid retraining on each request
            pred = predict_cached([processed], model_choice)[0]
            score = predict_score_cached([processed])[0]
        
        # Format output
        sentiment_map = {'positive': 'Positive', 'neutral': 'Neutral', 'negative': 'Negative'}
        sentiment = sentiment_map.get(str(pred).lower(), str(pred))
        
        # Color based on sentiment
        card_color = 'success' if sentiment == 'Positive' else ('danger' if sentiment == 'Negative' else 'warning')
        
        return dbc.Card([
            dbc.CardBody([
                html.H5('Analysis Result', className='card-title'),
                html.Hr(),
                html.P([
                    html.Strong('Sentiment: '),
                    sentiment
                ], style={'fontSize': '1.2em'}),
                html.P([
                    html.Strong('Emotional Intensity Score: '),
                    f'{float(score):.3f}'
                ], style={'fontSize': '1.1em'}),
                html.Small(f'Model: {model_choice}')
            ])
        ], color=card_color, outline=True, className='text-center')
    
    except ValueError as e:
        # This catches the "Unknown model_name" error from my_model
        return dbc.Alert([
            html.Strong('Model Error: '),
            str(e)
        ], color='danger')
    
    except Exception as e:
        # Catch all other errors
        return dbc.Alert([
            html.Strong(f'Error ({type(e).__name__}): '),
            str(e),
            html.Br(),
            html.Small('Check the browser console (F12) for more details.')
        ], color='danger')
