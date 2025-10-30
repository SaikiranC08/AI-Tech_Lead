import os
import json
from flask import Flask, request, abort
import hmac
import hashlib
from dotenv import load_dotenv
import threading
from .crew import AITechLeadCrew

# --- Environment Variable Loading and Validation ---
load_dotenv()

required_vars = ["GITHUB_WEBHOOK_SECRET", "GITHUB_ACCESS_TOKEN", "GEMINI_API_KEY"]
missing_vars = [var for var in required_vars if not os.environ.get(var)]
if missing_vars:
    raise ValueError(f"CRITICAL ERROR: Missing required environment variables: {', '.join(missing_vars)}")

GITHUB_WEBHOOK_SECRET_STR = os.environ.get('GITHUB_WEBHOOK_SECRET')
GITHUB_WEBHOOK_SECRET = GITHUB_WEBHOOK_SECRET_STR.encode('utf-8')
# --- End of Validation ---

app = Flask(__name__)

def verify_signature(payload_body, signature_header):
    """Verify that the payload was sent from GitHub."""
    if not signature_header:
        raise ValueError("Signature verification failed: x-hub-signature-256 header is missing!")
    
    hash_object = hmac.new(GITHUB_WEBHOOK_SECRET, msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    if not hmac.compare_digest(expected_signature, signature_header):
        raise ValueError("Signature verification failed: Request signatures didn't match!")

def run_crew_in_background(repo_name, pr_number):
    """Function to run the CrewAI process in a separate thread."""
    print(f"Starting crew for {repo_name}# {pr_number} in a background thread.")
    try:
        crew_instance = AITechLeadCrew(repo_name, pr_number)
        crew_instance.run()
        print(f"Crew run finished successfully for {repo_name}# {pr_number}.")
    except Exception as e:
        print(f"CRITICAL ERROR during crew run for {repo_name}# {pr_number}: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    signature_header = request.headers.get('x-hub-signature-256')
    try:
        verify_signature(request.data, signature_header)
    except ValueError as e:
        print(f"--- SIGNATURE VERIFICATION FAILED: {e} ---")
        abort(403)

    if request.headers.get('x-github-event') == 'pull_request':
        payload = request.get_json()
        action = payload.get('action')

        if action in ['opened', 'synchronize']:
            repo_name = payload['repository']['full_name']
            pr_number = payload['number']
            
            print(f"+++ Webhook received and verified for PR: {repo_name}# {pr_number} +++")
            
            thread = threading.Thread(target=run_crew_in_background, args=(repo_name, pr_number))
            thread.start()
            
            return 'Webhook received. Kicking off review process in the background.', 202
            
    return 'Event not processed.', 200

if __name__ == '__main__':
    print("--- Starting Flask Server ---")
    print("Watcher is listening for GitHub webhooks on port 5001...")
    app.run(port=5001, debug=False)