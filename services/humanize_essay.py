import time
import requests
from config import HIX_API_KEY, HUMANISE_SUBMIT_URL, HUMANISE_RETRIEVE_URL
from models.request_models import HumanizeEssay, HumanizeEssayResponse

hix_api_key = HIX_API_KEY

def humanize_essay_logic(essay_text : HumanizeEssay, max_retries=40, polling_interval=5):
    """Pass the essay through HIX Bypass API to humanize it."""
    start_time = time.time()
    url = HUMANISE_SUBMIT_URL
    headers = {
        "accept": "application/json",
        "api-key": hix_api_key,
        "Content-Type": "application/json"
    }
    data = {
        "input": essay_text.essay_txt,
        "mode": "Latest",  # Modes: "Fast", "Balanced", "Aggressive", "Latest"
        "language": "en"  # Specify English explicitly
    }
    
    try:
        # Submit the essay
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            task_id = result.get("data", {}).get("task_id", "")
            if not task_id:
                print("Task ID not found in submission response.")
                return None

            # Polling mechanism to retrieve the humanized text
            retrieval_url = f"{HUMANISE_RETRIEVE_URL}?task_id={task_id}"
            retries = 0
            while retries < max_retries:
                retrieval_response = requests.get(retrieval_url, headers=headers)
                if retrieval_response.status_code == 200:
                    retrieval_result = retrieval_response.json()
                    err_code = retrieval_result.get("err_code", 1)
                    output_text = retrieval_result.get("data", {}).get("output", None)

                    if output_text and err_code == 0:
                        print(f"Humanized essay retrieved successfully in {retries + 1} retries.")
                        end_time = time.time()
                        execution_time = end_time - start_time
                        print(f"Humanize generation logic executed in {execution_time:.2f} seconds for {len(output_text.split())} words.")
                        return HumanizeEssayResponse(humanized_essay=output_text)

                time.sleep(polling_interval)  # Wait before retrying
                retries += 1

            print("Max retries reached. Could not retrieve humanized essay.")
            return None

        else:
            print(f"Failed to submit essay. Status Code: {response.status_code}")
            return None

    except requests.RequestException as e:
        print(f"Request error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None
