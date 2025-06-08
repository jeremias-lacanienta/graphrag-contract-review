import os
import json
import time
import PyPDF2
import sys
from dotenv import load_dotenv
from openai import AzureOpenAI
import re

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Utils import read_text_file, save_json_string_to_file, extract_json_from_string

# Load environment variables from .env file
load_dotenv()

# Configure Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT')

# Check if Azure OpenAI configuration is available
if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_DEPLOYMENT:
    print("Azure OpenAI configuration not found. Please add to your .env file:")
    print("AZURE_OPENAI_API_KEY=your-key")
    print("AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
    print("AZURE_OPENAI_DEPLOYMENT=your-deployment-name")
    exit(1)

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2023-05-15",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Load the system instruction and extraction prompt
system_instruction = read_text_file('./prompts/system_prompt.txt')
extraction_prompt = read_text_file('./prompts/contract_extraction_prompt.txt')

def process_pdf(pdf_filename):
    print(f"Processing {pdf_filename}...")
    
    # Extract text from PDF
    pdf_text = ""
    try:
        with open(pdf_filename, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                pdf_text += page.extract_text()
                
        print(f"Extracted {len(pdf_text)} characters of text from PDF")
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        raise
    
    # Create messages for the API call
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Here is the contract text:\n\n{pdf_text}\n\n{extraction_prompt}"}
    ]
    
    # Make the API call
    try:
        print(f"Sending request to Azure OpenAI ({AZURE_OPENAI_DEPLOYMENT})...")
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.0,
            max_tokens=4000
        )
        
        # Extract the response content
        completion_text = response.choices[0].message.content
        print(f"Received response ({len(completion_text)} characters)")
        
        return completion_text
    except Exception as e:
        print(f"Error calling Azure OpenAI: {e}")
        raise

def main():
    # Create necessary directories if they don't exist
    os.makedirs('./data/debug', exist_ok=True)
    os.makedirs('./data/output', exist_ok=True)
    
    # Get list of PDF files
    pdf_files = [filename for filename in os.listdir('./data/input/') if filename.endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found in ./data/input/ directory")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_filename in pdf_files:
        try:
            print(f"\nProcessing {pdf_filename}...")
            
            # Extract content from PDF
            complete_response = process_pdf(f'./data/input/{pdf_filename}')
            
            # Log the complete response for debugging
            save_json_string_to_file(complete_response, f'./data/debug/complete_response_{pdf_filename}.json')
            
            # Try to load the response as valid JSON
            try:
                contract_json = extract_json_from_string(complete_response)
                json_string = json.dumps(contract_json, indent=4)
                save_json_string_to_file(json_string, f'./data/output/{pdf_filename}.json')
                print(f"Successfully extracted and saved JSON for {pdf_filename}")
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON: {e}")
                print("Check the debug output for the complete response")
        except Exception as e:
            print(f"Error processing {pdf_filename}: {e}")

if __name__ == '__main__':
    main()
