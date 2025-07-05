from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Use PORT from environment (for Render) or default to 3000 for local dev
    port = int(os.environ.get("PORT", 5000))  # Render uses PORT, locally 3000
    debug = os.environ.get("FLASK_ENV") == "development"  # Debug mode in dev only
    
    # Run the app
    app.run(host="0.0.0.0", port=port, debug=debug)

"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
"""