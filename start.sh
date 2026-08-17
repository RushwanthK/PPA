#!/bin/sh

echo "Applying database migrations..."
flask db upgrade

echo "Starting Flask application..."
python run.py